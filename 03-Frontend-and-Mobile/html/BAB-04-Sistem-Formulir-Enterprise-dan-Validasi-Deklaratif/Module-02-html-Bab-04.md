# Kurikulum Rekayasa Perangkat Lunak Enterprise: Web Platform & Architecture
## Bab 04: Sistem Formulir Enterprise dan Validasi Deklaratif
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Enterprise Architect / Principal Engineer diharapkan memiliki kapabilitas terukur untuk:

1. **Mendesain dan Mengimplementasikan Form-Associated Custom Elements (FACE)** menggunakan API `ElementInternals` untuk mengabstraksi kontrol input kompleks ke dalam Web Components native tanpa kehilangan integrasi siklus hidup form native.
2. **Membangun Arsitektur Validasi Multi-Tier Declarative-Reactive** yang memanfaatkan native `ValidityState` interface, custom validity pipeline, dan event loop synchronization tanpa menyebabkan *forced synchronous layout* atau ketergantungan pada pustaka pihak ketiga.
3. **Mengorkestrasikan Multi-Step Form State Machine** berskala besar dengan integritas serialisasi data, penanganan persistensi transien (*session recovery*), dan kompatibilitas *offline-first* menggunakan `FormData` dan browser storage.
4. **Menerapkan Standar Keamanan & Kepatuhan Data Tingkat Lanjut** mencakup mitigasi Cross-Site Scripting (DOM-based XSS via form input), pencegahan autofill abuse berbasis PCI-DSS/GDPR, tokenisasi CSRF native, dan optimasi sub-resource integrity saat pengiriman binary/multipart data.
5. **Mengisolasi dan Mengoptimalkan Kinerja Form Rendering** pada form berdensitas data tinggi (100+ input fields) dengan zero layout thrashing, micro-optimizations pada input bubbling, dan integrasi Accessibility (WCAG 2.1 Level AA) berbasis ARIA Live Regions native.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus telah menguasai:
* **HTML5 Constraint Validation API Fundamental**: Pemahaman tentang atribut `pattern`, `required`, `minlength`, `maxlength`, tipe input native, dan pseudo-classes CSS (`:valid`, `:invalid`, `:user-invalid`).
* **Web Components Core Specifications**: Custom Elements v1, Shadow DOM v1, dan *lifecycle callbacks* (`connectedCallback`, `attributeChangedCallback`).
* **Event Loop & Asynchronous Microtasks**: Paham mendalam mengenai `requestAnimationFrame`, `queueMicrotask`, dan prioritisasi event input (`beforeinput`, `input`, `change`, `invalid`).
* **HTTP Protocol & Payload Encodings**: Struktur dari `application/x-www-form-urlencoded`, `multipart/form-data`, dan streaming multipart upload.

---

### 3. Concept & Internal Architecture

#### 3.1 Siklus Hidup Native Form Submission & Validasi di Browser Engine

Di balik eksekusi `<form>`, browser engine (Blink/Gecko/WebKit) menjalankan pipeline submission berbasis state machine bawaan C++:

```
[User Trigger: Submit Event]
            │
            ▼
[Check HTMLFormElement.noValidate]
   ├── true  ──► [Bypass Constraint Validation API] ──────────────────────────┐
   └── false ──► [Run Constraint Validation Algorithm]                        │
                        │                                                     │
                        ├── Any element invalid?                              │
                        │       ├── YES: Fire 'invalid' event per element*    │
                        │       │        (Cancelable, Non-Bubbling)           │
                        │       │        Focus first invalid element          │
                        │       │        Render default browser UI popup      │
                        │       │        ABORT Submission Pipeline            │
                        │       │                                             │
                        │       └── NO: Continue Submission                   │
                        │                                                     │
                        ▼                                                     │
[Fire 'submit' event on HTMLFormElement] (Cancelable, Bubbling)               │
   ├── e.preventDefault() triggered?                                          │
   │       └── YES: HALT Pipeline (Custom Ajax / Fetch Handover)              │
   │       └── NO: Continue Native Submission ◄───────────────────────────────┘
   ▼
[Construct Entry List (Constructing the Form Data Set)]
   ├── Iterate submittable elements in tree order
   ├── Ignore: disabled, buttons not clicked, unchecked radio/checkboxes
   └── Trigger Form-Associated Custom Elements (formdata event / getFormValue)
   ▼
[Encode Payload based on enctype]
   ├── application/x-www-form-urlencoded
   ├── multipart/form-data
   └── text/plain
   ▼
[Dispatch HTTP Request via Networking Stack]
```
*\*Catatan Arsitektural Penting: Event `invalid` **tidak melakukan bubbling** (bubbles: false). Ini membedakannya secara fundamental dari event `input` atau `submit`.*

#### 3.2 Anatomi Mendalam `ValidityState` Interface

Setiap elemen input native dan Form-Associated Custom Element mengimplementasikan objek `ValidityState`. Browser secara otomatis mengevaluasi bitmask internal ini setiap kali nilai atau atribut berubah:

| Bendera (Flag) | Penyebab Aktivasi (Faktor Pemicu) | Sifat Evaluasi |
| :--- | :--- | :--- |
| `valueMissing` | Input memiliki atribut `required`, namun nilainya kosong. | Deklaratif Native |
| `typeMismatch` | Tipe data tidak sesuai dengan nilai (misal: input `type="email"` atau `type="url"`). | Parsing Sintaks Regex Internal |
| `patternMismatch`| Nilai tidak sesuai dengan ekspresi reguler pada atribut `pattern`. | Native RegExp Engine |
| `tooLong` | Panjang string melebihi atribut `maxlength` (diedit pengguna). | String UTF-16 Code Units |
| `tooShort` | Panjang string kurang dari atribut `minlength`. | String UTF-16 Code Units |
| `rangeUnderflow` | Nilai numerik/tanggal lebih kecil dari atribut `min`. | Parsing Value As Number/Date |
| `rangeOverflow` | Nilai numerik/tanggal lebih besar dari atribut `max`. | Parsing Value As Number/Date |
| `stepMismatch` | Nilai tidak berada pada interval yang valid sesuai atribut `step`. | Modulo Floating-point Arithmetic |
| `badInput` | Nilai input tidak dapat diubah ke tipe target (misal: huruf pada `type="number"`). | Engine Parser Failure |
| `customError` | Dipicu secara eksplisit via `setCustomValidity("Pesan Kesalahan")`. | Imperatif via JavaScript |
| `valid` | Bernilai `true` HANYA JIKA semua 10 bendera di atas bernilai `false`. | Logical AND Evaluator |

#### 3.3 Form-Associated Custom Elements (FACE) & `ElementInternals`

Sebelum pengenalan FACE via `attachInternals()`, Web Component berbasis Shadow DOM adalah "black-box" yang terisolasi dari form submission engine. Kontrol kustom memerlukan implementasi `<input type="hidden">` tersembunyi yang rentan sinkronisasi asinkron dan tidak mendukung native constraint validation.

Dengan FACE:
1. Kelas Web Component mendeklarasikan statis `static formAssociated = true;`.
2. Konstruktor memanggil `this.attachInternals()`, menghasilkan objek `ElementInternals`.
3. Objek `internals` ini mengekspos API form native: `setFormValue()`, `setValidity()`, `checkValidity()`, `reportValidity()`, dan `validationMessage`.
4. Browser Engine mendaftarkan Web Component sebagai *submittable element* kelas satu dalam algoritma Form Data Assembly.

---

### 4. Why & What

| Fitur / Masalah | Pendekatan Library Pihak Ketiga (e.g., Formik, React Hook Form) | Pendekatan Declarative Enterprise HTML Platform |
| :--- | :--- | :--- |
| **Alokasi Memori & Bundle Size** | 15KB - 60KB runtime bundle. Alokasi ribuan object closure pada nested state. | **0 KB bundle overhead**. Memory footprint dikelola langsung oleh C++ heap browser. |
| **Siklus Validasi UI** | Membutuhkan re-render siklus Virtual DOM atau subscription update listener. | Berjalan langsung pada composite pipeline; sinkronisasi otomatis status CSS `:user-invalid` dan native `:invalid`. |
| **Konsistensi Aksesibilitas (a11y)** | Manual; developer harus menautkan `aria-describedby` ke tag error secara imperatif. | Native browser tooltips secara otomatis terikat pada Accessibility Tree (AT) OS. |
| **Shadow DOM Encapsulation** | Bocor atau sulit mengontrol validasi input di dalam custom elements. | Integrasi tanpa celah via `ElementInternals` API. |
| **Ketahanan Degradasi (Resilience)** | Jika JavaScript crash atau parsing bundel gagal, form menjadi *dead element*. | Mendukung *Progressive Enhancement*; fallback ke submit native browser tetap berfungsi. |

---

### 5. How (Workflow Detail)

Untuk mengimplementasikan arsitektur formulir enterprise yang *robust*:

1. **Inisialisasi Custom Element**: Registrasikan elemen dengan Shadow DOM dan definisikan kontrak form association.
2. **Setup ElementInternals**: Ikat referensi internals pada custom element untuk interaksi langsung ke parent `<form>`.
3. **Konstruksi Validation Rules**: Terjemahkan schema validasi bisnis ke dalam bitmask native menggunakan `internals.setValidity()`.
4. **Sinkronisasi Input Event**: Manfaatkan lifecycle `formResetCallback`, `formDisabledCallback`, dan `formAssociatedCallback`.
5. **Penanganan Validasi Global**: Gunakan bubbling capture pada form level dengan mengintercept event `invalid` melalui listener fase *capture*.
6. **Eksekusi Submission**: Tangani via interceptor submission (`submit` event) untuk serialisasi payload transaksional atau fallback langsung ke native transport engine.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional dan Jalur Bea Cukai (Customs Gate)

Bayangkan form submission sebagai sebuah **Jalur Pemeriksaan Keberangkatan Bandara**:
* **`<form>` Element**: Terminal keberangkatan.
* **Input Elements & FACE**: Penumpang yang membawa dokumen.
* **`ValidityState` Flags**: Checklist petugas imigrasi (Paspor kedaluwarsa? Visa tidak valid? Tiket cocok?).
* **`setCustomValidity`**: Petugas khusus yang menandai penumpang bermasalah dengan catatan manual.
* **`invalid` Event**: Alarm yang berbunyi seketika di bilik pemeriksaan tertentu (tidak bergaung ke seluruh terminal / *no-bubbling*).
* **`ElementInternals`**: Paspor Diplomatik resmi yang diberikan kepada delegasi independen (Web Components) sehingga mereka diperlakukan sama persis seperti penumpang native reguler oleh sistem otomatis bandara.

#### Diagram Arsitektur Form Lifecycle & FACE

```
+-----------------------------------------------------------------------------------+
| Browser Render Process                                                            |
|                                                                                   |
|  <form id="tx-form">                                                              |
|    |                                                                              |
|    +--> <input type="text" required pattern="[A-Z]{3}">                          |
|    |      |                                                                       |
|    |      +--> Internal Native Engine Checks (valueMissing, patternMismatch)      |
|    |                                                                              |
|    +--> <custom-currency-field name="amount" required>                            |
|           |                                                                       |
|           |  Shadow DOM Boundary                                                  |
|           |  ┌────────────────────────────────────────────────────────┐          |
|           |  │ [Inner <input type="text">]                            │          |
|           |  │     │                                                  │          |
|           |  │     ▼ Parse Raw Currency Formatting ("$ 1,250.00")     │          |
|           |  │     │                                                  │          |
|           |  │ [ElementInternals]                                     │          |
|           |  │     │                                                  │          |
|           |  │     ├── .setFormValue("1250.00")                       │          |
|           |  │     └── .setValidity({ customError: true }, "Min $2k") │          |
|           |  └────────────────────────┬───────────────────────────────┘          |
|                                       │                                           |
|                  Exposes Interface to Outside Tree                                |
|                                       ▼                                           |
|                         [HTMLFormElement Engine]                                  |
|                                       │                                           |
|                  +--------------------+--------------------+                      |
|                  | Form Validation Phase                   |                      |
|                  | (Check validity flags on all controls)  |                      |
|                  +--------------------+--------------------+                      |
|                                       │                                           |
|                         ┌─────────────┴─────────────┐                             |
|                         │                           │                             |
|                      [FAIL]                      [PASS]                           |
|                         │                           │                             |
|         Fire 'invalid' at Target Controls   Dispatch 'submit' Event               |
|         (Focus first invalid element)               │                             |
|                                             [FormData Engine]                     |
|                                             Collect all FormValues                |
|                                                     │                             |
|                                             [Network Transport]                   |
+-----------------------------------------------------------------------------------+
```

---

### 7. Code Examples

#### 7.1 Simple Example: Dynamic Validation Rule Override Menggunakan `ValidityState`

Implementasi pemantauan validitas deklaratif native tanpa library, dengan kustomisasi pesan kesalahan yang sinkron dengan accessibility tree.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Constraint Validation Showcase</title>
  <style>
    .field-group { margin-bottom: 1.5rem; display: flex; flex-direction: column; }
    .error-msg { color: #d32f2f; font-size: 0.875rem; display: none; margin-top: 0.25rem; }
    input:user-invalid { border: 2px solid #d32f2f; background-color: #fde8e8; }
    input:user-valid { border: 2px solid #2e7d32; }
    input:user-invalid + .error-msg { display: block; }
  </style>
</head>
<body>
  <form id="registration-form" novalidate>
    <div class="field-group">
      <label for="org-code">Kode Organisasi (3 Kapital & 2 Digit):</label>
      <input 
        type="text" 
        id="org-code" 
        name="orgCode" 
        required 
        pattern="^[A-Z]{3}\d{2}$" 
        placeholder="ABC12" 
        aria-describedby="org-code-error"
      />
      <span class="error-msg" id="org-code-error" role="alert"></span>
    </div>
    <button type="submit">Validasi Data</button>
  </form>

  <script>
    const form = document.getElementById('registration-form');
    const orgInput = document.getElementById('org-code');
    const errorSpan = document.getElementById('org-code-error');

    function syncValidationState(input, errorElement) {
      if (input.validity.valid) {
        errorElement.textContent = '';
        input.setCustomValidity('');
        return;
      }

      // Memeriksa flags spesifik dari ValidityState
      if (input.validity.valueMissing) {
        input.setCustomValidity('Kode organisasi wajib diisi.');
      } else if (input.validity.patternMismatch) {
        input.setCustomValidity('Format harus 3 huruf besar diikuti 2 angka (misal: JKT01).');
      } else {
        input.setCustomValidity('Nilai tidak valid.');
      }

      errorElement.textContent = input.validationMessage;
    }

    orgInput.addEventListener('input', () => {
      // Reset custom error agar validity recalculation berjalan native
      orgInput.setCustomValidity('');
      syncValidationState(orgInput, errorSpan);
    });

    form.addEventListener('submit', (e) => {
      syncValidationState(orgInput, errorSpan);
      if (!form.checkValidity()) {
        e.preventDefault();
        orgInput.reportValidity();
      } else {
        e.preventDefault();
        alert('Form lolos validasi declarative native!');
      }
    });
  </script>
</body>
</html>
```

#### 7.2 Practical Example: Enterprise-Grade Form-Associated Custom Element (FACE)

Elemen Custom Input `<enterprise-currency-input>` yang merangkum input formatting Shadow DOM namun berpartisipasi penuh dalam validasi form native dan serialisasi payload.

```typescript
// File: src/components/enterprise-currency-input.ts

export class EnterpriseCurrencyInput extends HTMLElement {
  static formAssociated = true;

  private internals: ElementInternals;
  private shadow: ShadowRoot;
  private inputElement!: HTMLInputElement;
  private _value: number | null = null;

  static get observedAttributes() {
    return ['value', 'min', 'max', 'required', 'disabled'];
  }

  constructor() {
    super();
    this.internals = this.attachInternals();
    this.shadow = this.attachShadow({ mode: 'open' });
    this.render();
  }

  private render() {
    this.shadow.innerHTML = `
      <style>
        :host { display: inline-block; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .wrapper { position: relative; display: flex; align-items: center; }
        .currency-prefix { position: absolute; left: 10px; color: #555; pointer-events: none; }
        input {
          padding: 8px 8px 8px 36px;
          border: 1px solid #ccc;
          border-radius: 4px;
          font-size: 1rem;
          width: 100%;
          box-sizing: border-box;
        }
        :host(:state(invalid)) input { border-color: #b71c1c; }
      </style>
      <div class="wrapper">
        <span class="currency-prefix">IDR</span>
        <input type="text" inputmode="numeric" />
      </div>
    `;
    this.inputElement = this.shadow.querySelector('input')!;
    this.bindEvents();
  }

  private bindEvents() {
    this.inputElement.addEventListener('input', (e) => {
      e.stopPropagation();
      const rawValue = this.inputElement.value.replace(/\D/g, '');
      const numericValue = rawValue ? parseInt(rawValue, 10) : null;
      this.setValue(numericValue);
      this.validate();
      this.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    });
  }

  private setValue(val: number | null) {
    this._value = val;
    if (val === null) {
      this.inputElement.value = '';
      this.internals.setFormValue(null);
    } else {
      this.inputElement.value = new Intl.NumberFormat('id-ID').format(val);
      // Serialisasi data murni ke form submission parent (bukan string hasil masking)
      this.internals.setFormValue(val.toString());
    }
  }

  public validate() {
    const isRequired = this.hasAttribute('required');
    const min = this.hasAttribute('min') ? Number(this.getAttribute('min')) : null;
    const max = this.hasAttribute('max') ? Number(this.getAttribute('max')) : null;

    if (isRequired && (this._value === null || isNaN(this._value))) {
      this.internals.setValidity(
        { valueMissing: true }, 
        'Bidang transaksi nominal ini wajib diisi.', 
        this.inputElement
      );
      return;
    }

    if (min !== null && this._value !== null && this._value < min) {
      this.internals.setValidity(
        { rangeUnderflow: true }, 
        `Nilai minimum transaksi adalah IDR ${new Intl.NumberFormat('id-ID').format(min)}.`, 
        this.inputElement
      );
      return;
    }

    if (max !== null && this._value !== null && this._value > max) {
      this.internals.setValidity(
        { rangeOverflow: true }, 
        `Nilai maksimum transaksi adalah IDR ${new Intl.NumberFormat('id-ID').format(max)}.`, 
        this.inputElement
      );
      return;
    }

    // Bersihkan validity jika lolos semua aturan
    this.internals.setValidity({});
  }

  // Lifecycle Callbacks FACE
  formResetCallback() {
    this.setValue(null);
    this.validate();
  }

  formDisabledCallback(disabled: boolean) {
    this.inputElement.disabled = disabled;
  }

  attributeChangedCallback(name: string, oldValue: string, newValue: string) {
    if (oldValue === newValue) return;
    if (name === 'value') this.setValue(newValue ? parseInt(newValue, 10) : null);
    if (name === 'disabled') this.inputElement.disabled = this.hasAttribute('disabled');
    this.validate();
  }

  // Mengizinkan parent element mengakses properti validity standar
  get validity() { return this.internals.validity; }
  get validationMessage() { return this.internals.validationMessage; }
  get willValidate() { return this.internals.willValidate; }
  checkValidity() { return this.internals.checkValidity(); }
  reportValidity() { return this.internals.reportValidity(); }
}

customElements.define('enterprise-currency-input', EnterpriseCurrencyInput);
```

---

### 8. Real World Case Study: Platform FinTech Multi-Stage KYC & Loan Origination

#### 8.1 Konteks Masalah
Sebuah platform perbankan digital enterprise menghadapi masalah *abandonment rate* 38% pada formulir registrasi pinjaman bisnis (*business loan*). Formulir tersebut memiliki:
* 6 tahap pengisian (*multi-step wizard*).
* 80+ data field termasuk unggah dokumen PDF/TIFF berukuran besar.
* Kebutuhan kepatuhan regulasi ketat: OJK dan PCI-DSS.

**Bottleneck Utama**: Arsitektur lama berbasis single massive state di framework JavaScript yang melakukan re-render toàn bộ DOM tree setiap penekanan tombol (*keystroke*). Latensi pengetikan mencapai >120ms pada perangkat low-end, terjadi kebocoran memori dari object references, dan pengiriman payload besar gagal saat sinyal seluler fluktuatif.

#### 8.2 Desain Solusi Arsitektur
Arsitektur didesain ulang dengan pola **Decoupled Declarative State Machine**:

```
[Form View Engine] 
   └── Multi-Step Screen Wrapper (HTML <form> partitioned into <fieldset> segments)
           │
           ├── Tier 1: Input Level Validation (Autonomous FACE + Declarative Constraint API)
           ├── Tier 2: Fieldset Validation (Cross-field integrity verification)
           └── Tier 3: Asynchronous KYC Gateway (Edge worker verification)
                   │
                   ▼
       [IndexedDB Transient Cache] <── (Local Snapshot every field change)
                   │
                   ▼
     [Native FormData Serializer]
                   │
                   ▼ (Streaming chunked upload via Fetch + ReadableStream)
       [Fintech Core API Service]
```

1. **Partisi Tahapan via `<fieldset>`**: Tiap *step* diletakkan dalam `<fieldset>` tersendiri. Navigasi *step* memanfaatkan `fieldset.disabled = true/false` dan `hidden`. Browser secara native mengecualikan elemen yang di-disable dari validasi dan data assembly form tahap yang sedang tersembunyi.
2. **Eliminasi UI Re-renders**: State dikelola langsung oleh DOM tree. Komponen hanya menggunakan native events (`input`, `change`) dan menangkap siklus validasi lewat delegasi `form.checkValidity()`. Latensi input berkurang dari 120ms ke **< 4ms** (*zero frame drops*).
3. **Persistensi Transien**: Menggunakan `FormData(form)` yang diserialisasikan ke `IndexedDB` setiap kali terjadi event `change` ter-debounce. Jika tab browser tertutup tiba-tiba, form dapat memulihkan state 100% tanpa mengorbankan keamanan data credential (PCI-DSS compliance menetapkan data sensitif seperti CVV tidak disimpan di IndexedDB).

---

### 9. Trade-offs & Engineering Matrix

| Dimensi Arsitektural | Declarative Native HTML Forms + FACE | Centralized UI Framework (e.g., Formik / React Hook Form) |
| :--- | :--- | :--- |
| **Kinerja Rendering (CPU Bound)** | **Sangat Tinggi**: Manipulasi atribut native dan bitmask C++ browser. Nol rendering cost di JavaScript heap. | **Sedang - Rendah**: Membutuhkan reconciler Virtual DOM, perbandingan state tree secara diffing, dan micro-subscriptions. |
| **Memori Footprint** | **Minimal**: Input values hidup di dalam C++ representation of DOM. | **Tinggi**: Duplikasi nilai di C++ DOM Node dan Javascript Runtime Memory Heap. |
| **Cross-Field Validation Kompleks** | **Moderat**: Perlu sedikit plumbing imperatif via `element.setCustomValidity()` dan event orchestration form-level. | **Sangat Nyaman**: Resolver schema terpusat (Zod, Yup) memudahkan aturan cross-field secara fungsional. |
| **Pemisahan Gaya UI (Customizability)** | **Tinggi (Shadow DOM)**: Sangat solid menggunakan encapsulasi Shadow DOM, namun browser native error tooltips sulit di-style secara universal. | **Sangat Fleksibel**: Seluruh state error berupa JS object yang bebas dirender menggunakan komponen UI apapun. |
| **Maintenance Burden Jangka Panjang** | **Sangat Rendah**: Mengikuti spesifikasi W3C/WHATWG yang stabil selama beberapa dekade tanpa risiko *breaking changes* vendor pustaka. | **Tinggi**: Bergantung pada kompatibilitas versi pustaka, migrasi API framework, dan pemeliharaan dependensi luar. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Silent Validation Failure Akibat Non-Bubbling `invalid` Event
* **Gejala Masalah**: Validasi global di level form menggunakan `form.addEventListener('invalid', callback)` tidak pernah terpanggil.
* **Akar Penyebab (Root Cause)**: Sesuai spesifikasi W3C HTML5, event `invalid` didesain dengan flag `bubbles: false`. Event ini hanya dipicu langsung pada target elemen yang gagal divalidasi.
* **Solusi Perbaikan**: Gunakan event listener pada fase penangkapan (*Capture Phase*):
  ```javascript
  // SALAH: Listener tidak akan pernah terpicu
  form.addEventListener('invalid', (e) => handleError(e));

  // BENAR: Pasang flag capture: true
  form.addEventListener('invalid', (e) => {
    handleError(e.target);
  }, true);
  ```

#### 10.2 Broken Layout Akibat Terjadinya Forced Synchronous Layout saat Validasi Massal
* **Gejala Masalah**: Frame rate anjlok (*jank*) drastis saat memvalidasi form yang memiliki 100+ inputs secara serempak.
* **Akar Penyebab**: Membaca properti layout seperti `offsetHeight` atau memicu `reportValidity()` secara loop imperatif, diikuti oleh manipulasi style secara bergantian, memaksa browser melakukan *recalculate style* dan *reflow* berulang kali.
* **Solusi Perbaikan**: Pisahkan fase pembacaan (*Read phase*) dan penulisan (*Write phase*):
  ```javascript
  // Batch checkValidity (Read)
  const invalidElements = [];
  for (const element of form.elements) {
    if (!element.checkValidity()) {
      invalidElements.push(element);
    }
  }

  // Batch DOM mutation (Write) via requestAnimationFrame
  requestAnimationFrame(() => {
    invalidElements.forEach(el => {
      el.classList.add('is-invalid');
      el.setAttribute('aria-invalid', 'true');
    });
    if (invalidElements.length > 0) {
      invalidElements[0].focus();
    }
  });
  ```

#### 10.3 Kebocoran Aksesibilitas (Accessible Tooltip Failure)
* **Gejala Masalah**: Pengguna screen-reader tidak menerima notifikasi alasan kegagalan validasi.
* **Solusi**: Jangan pernah bergantung hanya pada indikator visual (seperti warna border merah). Selalu hubungkan elemen input secara terprogram ke elemen teks penjelas error melalui `aria-describedby` dan manfaatkan kontainer `role="alert"` atau `aria-live="assertive"`.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Non-Destructive Constraint Validation**: Gunakan CSS selector `:user-invalid` (bukan `:invalid`) untuk mencegah kontrol formulir langsung menyala merah sebelum pengguna sempat mengetik (*initial pristine state*).
2. [ ] **Enforce Autocomplete Tokens**: Cantumkan atribut `autocomplete` sesuai spesifikasi WHATWG (misal: `autocomplete="billing street-address"`, `autocomplete="one-time-code"`) untuk mempercepat pengisian dan mencegah *autofill hijacking*.
3. [ ] **No Validate Overrides for APIs**: Selalu gunakan atribut `novalidate` pada form yang sepenuhnya diorkestrasi via Ajax/Fetch untuk mencegah kemunculan default *speech-bubble tooltip* browser yang tidak konsisten antar-sistem operasi, sembari tetap mempertahankan fungsi internal Constraint Validation API via code.
4. [ ] **Zero Sensitive Storage**: Pastikan data sensitif perbankan/kriptografis memiliki atribut `autocomplete="off"` dan tidak pernah disimpan di storage sisi klien (`localStorage`/`sessionStorage`/`IndexedDB`).
5. [ ] **Submittable Element Performance**: Batasi penggunaan *deeply nested* Custom Elements di dalam Shadow DOM yang berat untuk mencegah overhead serialisasi saat inisialisasi `new FormData(form)`.
6. [ ] **Explicit Submission Handlers**: Pastikan setiap tombol pengirim memiliki tipe eksplisit: `type="submit"` atau `type="button"` untuk menghindari *accidental submissions* ketika tombol ditekan via tombol Enter.

---

### 12. Hands-on Practice

Buatlah implementasi formulir multi-langkah (*multi-tier form pipeline*) dengan validasi custom declarative native.

#### Langkah 1: Struktur Direktori
Siapkan folder untuk latihan ini:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
touch index.html app.js styles.css
```

#### Langkah 2: Kode HTML (`hands-on/m02/index.html`)
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Multi-Step Form Engine</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="container">
    <h1>Pendaftaran Merchant Enterprise</h1>
    
    <form id="enterprise-form" novalidate>
      <!-- STEP 1: Profil Entitas Bisnis -->
      <fieldset id="step-1" class="form-step">
        <legend>Langkah 1: Identitas Bisnis</legend>
        
        <div class="form-group">
          <label for="company-name">Nama Perusahaan Legal (PT/CV):</label>
          <input type="text" id="company-name" name="companyName" required minlength="4" maxlength="100">
          <span class="field-error" id="err-company-name" role="alert"></span>
        </div>

        <div class="form-group">
          <label for="tax-id">NPWP (15 Digit Numerik):</label>
          <input type="text" id="tax-id" name="taxId" required pattern="^\d{15}$" inputmode="numeric">
          <span class="field-error" id="err-tax-id" role="alert"></span>
        </div>

        <button type="button" class="btn-next" data-next="step-2">Lanjut ke Finansial &rarr;</button>
      </fieldset>

      <!-- STEP 2: Profil Finansial (Menggunakan Custom Element) -->
      <fieldset id="step-2" class="form-step" disabled hidden>
        <legend>Langkah 2: Proyeksi Transaksi</legend>

        <div class="form-group">
          <label for="initial-deposit">Deposit Operasional Awal:</label>
          <enterprise-currency-input 
            id="initial-deposit" 
            name="initialDeposit" 
            min="1000000" 
            required>
          </enterprise-currency-input>
          <span class="field-error" id="err-initial-deposit" role="alert"></span>
        </div>

        <div class="button-group">
          <button type="button" class="btn-prev" data-prev="step-1">&larr; Kembali</button>
          <button type="button" class="btn-next" data-next="step-3">Lanjut ke Dokumen &rarr;</button>
        </div>
      </fieldset>

      <!-- STEP 3: Dokumen & Submission -->
      <fieldset id="step-3" class="form-step" disabled hidden>
        <legend>Langkah 3: Konfirmasi Legalitas</legend>

        <div class="form-group">
          <label>
            <input type="checkbox" id="terms-agree" name="termsAgree" required>
            Saya menyetujui seluruh ketentuan audit dan kepatuhan sistem.
          </label>
          <span class="field-error" id="err-terms-agree" role="alert"></span>
        </div>

        <div class="button-group">
          <button type="button" class="btn-prev" data-prev="step-2">&larr; Kembali</button>
          <button type="submit" id="btn-submit">Finalisasi & Kirim Aplikasi</button>
        </div>
      </fieldset>
    </form>
  </main>

  <script type="module" src="app.js"></script>
</body>
</html>
```

#### Langkah 3: Kode CSS (`hands-on/m02/styles.css`)
```css
:root {
  --primary: #0d47a1;
  --danger: #b71c1c;
  --border: #cfd8dc;
  --bg-light: #eceff1;
}

body {
  font-family: system-ui, -apple-system, sans-serif;
  background-color: var(--bg-light);
  margin: 0;
  padding: 2rem;
  display: grid;
  place-content: center;
}

.container {
  width: 100%;
  max-width: 600px;
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}

fieldset {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

fieldset[hidden] {
  display: none;
}

.form-group {
  margin-bottom: 1.25rem;
  display: flex;
  flex-direction: column;
}

label {
  font-weight: 600;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

input[type="text"] {
  padding: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 1rem;
}

/* User-invalid feedback state */
input:user-invalid {
  border-color: var(--danger);
  outline-color: var(--danger);
}

.field-error {
  color: var(--danger);
  font-size: 0.8rem;
  margin-top: 0.25rem;
  min-height: 1rem;
}

.button-group {
  display: flex;
  gap: 1rem;
}

button {
  background-color: var(--primary);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.95rem;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-prev {
  background-color: #546e7a;
}
```

#### Langkah 4: Kode JavaScript (`hands-on/m02/app.js`)
```javascript
// Definisi Form-Associated Custom Element
class EnterpriseCurrencyInput extends HTMLElement {
  static formAssociated = true;

  constructor() {
    super();
    this.internals = this.attachInternals();
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        input {
          width: 100%;
          box-sizing: border-box;
          padding: 0.6rem;
          border: 1px solid #cfd8dc;
          border-radius: 4px;
          font-size: 1rem;
        }
      </style>
      <input type="text" placeholder="Rp 0" />
    `;
    this.input = this.shadowRoot.querySelector('input');
    this.rawValue = '';

    this.input.addEventListener('input', () => {
      this.rawValue = this.input.value.replace(/\D/g, '');
      const numeric = parseInt(this.rawValue, 10);
      
      if (!this.rawValue || isNaN(numeric)) {
        this.input.value = '';
        this.internals.setFormValue('');
      } else {
        this.input.value = new Intl.NumberFormat('id-ID', {
          style: 'currency',
          currency: 'IDR',
          maximumFractionDigits: 0
        }).format(numeric);
        this.internals.setFormValue(this.rawValue);
      }
      this.validate();
      this.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    });
  }

  validate() {
    const min = Number(this.getAttribute('min')) || 0;
    const val = parseInt(this.rawValue, 10);

    if (this.hasAttribute('required') && (!this.rawValue || isNaN(val))) {
      this.internals.setValidity({ valueMissing: true }, 'Nominal wajib diisi.', this.input);
    } else if (val < min) {
      this.internals.setValidity({ rangeUnderflow: true }, `Nominal minimal adalah Rp ${min.toLocaleString('id-ID')}.`, this.input);
    } else {
      this.internals.setValidity({});
    }
  }

  formResetCallback() {
    this.rawValue = '';
    this.input.value = '';
    this.internals.setFormValue('');
    this.validate();
  }

  get validity() { return this.internals.validity; }
  get validationMessage() { return this.internals.validationMessage; }
  checkValidity() { return this.internals.checkValidity(); }
  reportValidity() { return this.internals.reportValidity(); }
}
customElements.define('enterprise-currency-input', EnterpriseCurrencyInput);

// Orchestrator Wizard Form Logic
const form = document.getElementById('enterprise-form');

function validateFieldset(fieldset) {
  const controls = Array.from(fieldset.querySelectorAll('input, enterprise-currency-input'));
  let isStepValid = true;

  for (const control of controls) {
    const errorContainer = fieldset.querySelector(`#err-${control.id}`);
    
    // Trigger internal check
    if (control.validate) control.validate();
    
    if (!control.checkValidity()) {
      isStepValid = false;
      if (errorContainer) {
        errorContainer.textContent = control.validationMessage || 'Bidang ini tidak valid.';
      }
    } else {
      if (errorContainer) errorContainer.textContent = '';
    }
  }
  return isStepValid;
}

// Navigasi Maju
document.querySelectorAll('.btn-next').forEach(btn => {
  btn.addEventListener('click', (e) => {
    const currentStep = e.target.closest('fieldset');
    const targetStepId = e.target.dataset.next;
    const targetStep = document.getElementById(targetStepId);

    if (validateFieldset(currentStep)) {
      currentStep.hidden = true;
      currentStep.disabled = true;

      targetStep.hidden = false;
      targetStep.disabled = false;
      targetStep.querySelector('input, enterprise-currency-input')?.focus();
    }
  });
});

// Navigasi Mundur
document.querySelectorAll('.btn-prev').forEach(btn => {
  btn.addEventListener('click', (e) => {
    const currentStep = e.target.closest('fieldset');
    const targetStepId = e.target.dataset.prev;
    const targetStep = document.getElementById(targetStepId);

    currentStep.hidden = true;
    currentStep.disabled = true;

    targetStep.hidden = false;
    targetStep.disabled = false;
  });
});

// Capture non-bubbling invalid event for reactive messaging
form.addEventListener('invalid', (e) => {
  const target = e.target;
  const parentStep = target.closest('fieldset');
  if (parentStep) {
    const err = parentStep.querySelector(`#err-${target.id}`);
    if (err) err.textContent = target.validationMessage;
  }
}, true);

// Reset error text on input
form.addEventListener('input', (e) => {
  const target = e.target;
  const parentStep = target.closest('fieldset');
  if (parentStep) {
    const err = parentStep.querySelector(`#err-${target.id}`);
    if (err && target.checkValidity()) err.textContent = '';
  }
});

// Handle Final Submission
form.addEventListener('submit', (e) => {
  e.preventDefault();
  const step3 = document.getElementById('step-3');
  
  if (validateFieldset(step3) && form.checkValidity()) {
    const data = new FormData(form);
    console.log('--- PAYLOAD SUBMISSION FINAL ---');
    for (let [key, val] of data.entries()) {
      console.log(`${key}: ${val}`);
    }
    alert('Formulir Enterprise Berhasil Dikirim!');
  }
});
```

---

### 13. Exercises

#### Level Easy:
Tambahkan kontrol native `input type="url"` untuk URL Profil LinkedIn Perusahaan pada Langkah 1.
* **Syarat**: Wajib menggunakan protokol HTTPS (misal: regex pattern validation), required, dan pesan kesalahan otomatis menggunakan bahasa Indonesia jika skema HTTP biasa terdeteksi.

#### Level Medium:
Implementasikan mekanisme *Save & Resume Form State*:
* Setiap kali pengguna memicu event `change` pada form, kumpulkan seluruh data ke sebuah objek via `new FormData(form)`.
* Simpan ke dalam `sessionStorage`.
* Buat modul inisialisasi yang saat halaman di-*refresh*, data dipulihkan kembali ke setiap kontrol formulir yang bersangkutan secara otomatis.

#### Level Hard:
Buatlah Form-Associated Custom Element kedua bernama `<enterprise-file-validator>`:
* Menerima input file native di dalam Shadow DOM.
* Memvalidasi bahwa file yang diunggah harus berekstensi `.pdf`, ukuran tepat di bawah 5MB, dan memverifikasi *Magic Bytes* file (ASCII header `%PDF-`) melalui pembacaan `FileReader` / `ArrayBuffer` asinkron.
* Set validity state menggunakan `this.internals.setValidity()` sehingga formulir tidak bisa di-*submit* jika dokumen PDF rusak (*tampered*) meskipun nama ekstensinya diubah secara manipulatif oleh user.

---

### 14. Challenge

**Studi Kasus Arsitektur**: Rancang sistem **Schema-Driven Form Engine** enterprise murni menggunakan Web Components dan Native Constraint Validation API tanpa framework JavaScript.

**Kebutuhan Sistem**:
1. Komponen menerima atribut tunggal: `<schema-form schema-url="/api/v1/schemas/kyc.json">`.
2. Engine melakukan *fetch* dan secara dinamis membangun form fields, memilih tipe native atau FACE, menerapkan native constraints (`pattern`, `min`, `max`, `step`, dsb.).
3. Eksekusi validasi cross-field dinamis: Misalnya, jika bidang `entityType === "CORPORATE"`, maka bidang `taxId` berubah menjadi `required` dan `pattern` bergeser dari format individu ke institusi secara runtime tanpa me-render ulang seluruh formulir.
4. Payload submission harus mempertahankan format nested JSON asli sesuai schema melalui interceptor `FormData` assembly algorithm native (`formdata` event).
5. Output code harus bebas dari *memory leaks* (tidak menyisakan unbinding event listeners saat elemen dihapus dari DOM).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa event `invalid` tidak dapat ditangkap menggunakan `form.addEventListener('invalid', handler)` biasa?**
   * *Jawaban*: Karena secara spesifikasi W3C, event `invalid` diinisialisasi dengan konfigurasi `bubbles: false`. Event ini tidak merambat ke atas pohon DOM. Untuk menangkapnya di tingkat parent `<form>`, penangan event harus didaftarkan pada fase penangkapan (*capture phase*) dengan `addEventListener('invalid', handler, true)`.

2. **Apa yang dikembalikan oleh properti `validity.valid` jika salah satu dari sepuluh bendera validitas (misal: `valueMissing`) bernilai `true`?**
   * *Jawaban*: Mengembalikan nilai boolean `false`. `validity.valid` bernilai `true` hanya jika seluruh bendera error berstatus `false`.

3. **Bagaimana cara membersihkan status error yang disetel via `element.setCustomValidity("Error")` agar kontrol formulir kembali valid?**
   * *Jawaban*: Dengan memanggil kembali metode tersebut menggunakan string kosong: `element.setCustomValidity('')`. Jika diberi string berisi spasi atau teks apapun, browser menganggap kontrol masih memiliki `customError: true`.

4. **Sebutkan pseudo-class CSS standar yang merepresentasikan input yang tidak valid HANYA SETELAH pengguna berinteraksi dengannya!**
   * *Jawaban*: `:user-invalid`. Berbeda dengan `:invalid` yang langsung aktif saat rendering awal jika input kosong dan `required`, `:user-invalid` hanya aktif setelah terjadi interaksi pengguna (*loss of focus* atau pengetikan).

5. **Apa fungsi utama deklarasi statis `static formAssociated = true;` pada implementasi Custom Element?**
   * *Jawaban*: Memberitahu browser engine bahwa kelas Web Component tersebut diizinkan bertindak sebagai Form-Associated Custom Element (FACE), memungkinkannya mengaitkan siklus hidup formulir native dan memanggil `attachInternals()`.

#### Bagian 2: Intermediate (5 Soal)
1. **Bagaimana cara mencegah browser menampilkan popup/speech bubble default saat validasi form native gagal ketika tombol submit ditekan?**
   * *Jawaban*: Menambahkan atribut boolean `novalidate` pada elemen `<form>`. Ini menonaktifkan pelaporan UI bawaan browser tetapi tetap mengizinkan penggunaan Constraint Validation API secara terprogram via JavaScript.

2. **Jelaskan peran metode `internals.setFormValue(value)` di dalam Form-Associated Custom Element!**
   * *Jawaban*: Metode ini mendaftarkan nilai yang akan diikutsertakan ke dalam objek `FormData` form submission. Tanpa pemanggilan metode ini, data internal dari Web Component tidak akan terkirim saat form di-submit secara native atau via serialisasi form.

3. **Mengapa elemen `<fieldset disabled>` sangat berguna dalam arsitektur formulir multi-langkah (wizard)?**
   * *Jawaban*: Ketika `<fieldset>` dinonaktifkan (`disabled`), seluruh elemen kontrol input di dalamnya otomatis dinonaktifkan secara serentak. Ini mencegah elemen di tahap yang tersembunyi memicu validasi error dan mengecualikan elemen-elemen tersebut dari submission `FormData` secara otomatis tanpa perlu manipulasi atribut individual.

4. **Apa perbedaan antara `checkValidity()` dan `reportValidity()`?**
   * *Jawaban*: `checkValidity()` hanya mengevaluasi status validasi dan mengembalikan boolean (`true`/`false`) tanpa mengubah tampilan UI. Sebaliknya, `reportValidity()` selain mengevaluasi dan mengembalikan boolean, juga memicu event `invalid` dan memunculkan notifikasi UI/fokus pada elemen pertama yang gagal divalidasi.

5. **Kapan siklus `formResetCallback()` pada `ElementInternals` dipanggil oleh browser?**
   * *Jawaban*: Siklus ini dieksekusi secara otomatis oleh engine browser ketika elemen form induknya menerima event `reset` (misalnya saat tombol `<button type="reset">` diklik atau metode `form.reset()` dipanggil via script).

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
1. **Skenario 1**: Pengguna mengunggah gambar profil 10MB pada form pendaftaran. Saat tombol submit ditekan, antarmuka browser mengalami *freeze* selama 800ms sebelum pesan kesalahan muncul. Setelah dianalisis, terjadi layout thrashing karena kode membaca validitas lalu mengatur class CSS error secara berulang di 50 elemen lain. Bagaimana cara memperbaikinya?
   * *Jawaban*: Pisahkan siklus pembacaan layout/validitas dari manipulasi DOM style (*batching*). Lakukan pembacaan seluruh elemen menggunakan `checkValidity()` terlebih dahulu, lalu jadwalkan seluruh pembaruan class CSS dan atribut ARIA ke dalam satu frame antrian render menggunakan `window.requestAnimationFrame()`. Hindari pemanggilan `reportValidity()` di dalam loop synchronous.

2. **Skenario 2**: Sistem perbankan Anda mewajibkan form transfer dana tidak boleh mengirimkan formatting rupiah (contoh: "Rp 1.000.000") ke backend, melainkan angka integer murni (`1000000`). Tim UI bersikeras pengguna harus tetap melihat titik pemisah ribuan saat mengetik. Bagaimana merancangnya menggunakan FACE tanpa library formatting tambahan?
   * *Jawaban*: Bangun custom element dengan Shadow DOM. Tampilkan string terformat pada input teks di dalam Shadow DOM untuk kenyamanan visual pengguna, namun pada saat event input terjadi, parse teks tersebut menjadi string numerik murni dan teruskan nilai murni tersebut ke browser form engine via `this.internals.setFormValue(cleanNumericString)`. Nilai yang diserialisasi ke backend akan otomatis berupa format data murni.

3. **Skenario 3**: Sebuah form enterprise dengan 10 tab fieldset mengalami bug di mana form tidak dapat di-submit, tidak ada pesan error di layar, dan tidak ada network request yang keluar. Apa penyebab paling logis dari sudut pandang arsitektur browser?
   * *Jawaban*: Terdapat elemen kontrol input yang memiliki atribut `required` atau `pattern` yang tidak terpenuhi di dalam salah satu fieldset/tab yang sedang tersembunyi (`display: none` atau `hidden`) namun **tidak** memiliki atribut `disabled`. Browser membatalkan submission karena elemen tersebut gagal validasi, namun gagal memfokuskan atau menampilkan speech bubble error karena elemen tersebut secara visual tidak terlihat (*unfocusable element*), menyebabkan eksekusi submission berhenti secara senyap (*silent abort*). Solusinya adalah menonaktifkan (`disabled`) seluruh fieldset yang sedang disembunyikan.

---

### 16. Summary

1. **Native Over External**: HTML5 Constraint Validation API dan `ElementInternals` menyediakan fondasi native berkemampuan tinggi untuk menangani seluruh spektrum validasi formulir tanpa ketergantungan pada runtime pustaka pihak ketiga.
2. **Kinerja Bebas Overhead**: Validasi deklaratif memanfaatkan evaluasi bitmask internal C++ engine browser, meniadakan rendering loop yang membebani alokasi memori pada form berskala besar.
3. **FACE Menghapus Keterbatasan Web Components**: Penggunaan `ElementInternals` menjembatani isolasi Shadow DOM, menjadikan Web Components peserta kelas satu dalam validasi, siklus hidup form, dan serialisasi data.
4. **Resilience & State Management**: Arsitektur enterprise yang sukses memisahkan partisi tahapan formulir menggunakan semantik native (`<fieldset disabled>`), menjamin keterpisahan data, mencegah kegagalan validasi tak terlihat, dan mempertahankan integritas data input sepanjang alur interaksi pengguna.