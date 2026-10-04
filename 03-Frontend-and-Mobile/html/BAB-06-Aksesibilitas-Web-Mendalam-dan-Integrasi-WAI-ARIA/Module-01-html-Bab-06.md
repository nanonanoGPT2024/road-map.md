# BAB 06 MODULE 01: Aksesibilitas Web Mendalam (A11y) & Integrasi WAI-ARIA

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum**: Frontend & Mobile Engineering (`03-Frontend-and-Mobile`)
* **Spesialisasi**: Core Web Technologies & Hypertext Systems Architecture
* **Topik/Modul**: Bab 06 Module 01 — Aksesibilitas Web Mendalam (A11y) & Integrasi WAI-ARIA
* **Tingkat Kompleksitas**: Advanced / Staff Engineer Track
* **Prasyarat Pengetahuan**: 
  * DOM API & Event Loop Architecture
  * Semantik Dokumen HTML5 (Living Standard)
  * CSS Box Model, Focus Rings, dan Visual Tree Rendering
  * JavaScript ES6+ (Event Bubbling, Keyboard Event Dispatching)
* **Estimasi Waktu Selesai**: 8–10 Jam Pelatihan Komprehensif

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar memiliki kemampuan untuk:

1. **Membedah & Memanipulasi Accessibility Tree**: Menganalisis bagaimana Document Object Model (DOM) diterjemahkan oleh browser engine ke dalam Platform Accessibility APIs secara deterministik.
2. **Menerapkan 4 Prinsip WCAG 2.2 (POUR)**: Mengimplementasikan persyaratan teknis WCAG level A, AA, dan AAA langsung ke dalam struktur markup dan layer skrip antarmuka.
3. **Mengoperasikan Pola WAI-ARIA 1.2/1.3**: Mengembangkan custom interactive widgets (seperti Modal Dialogs, Comboboxes, Listboxes, dan Tabs) dengan status, peran (*role*), dan relasi yang akurat tanpa merusak semantik natif.
4. **Mengatur Focus Management Tingkat Lanjut**: Mengimplementasikan programmatic focus trapping, roving tabindex, dan skip navigation links yang tahan terhadap rendering dinamis (SPA/Hydration).
5. **Mengintegrasikan Automated & Manual Accessibility Testing**: Menyematkan audit linting berbasis engine axe-core, pengujian screen reader (NVDA, VoiceOver), dan pengujian keyboard murni ke dalam siklus hidup CI/CD.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. The Dual-Tree Paradigm
Web developer pemula sering berasumsi bahwa browser hanya membangun satu pohon representasi dokumen, yaitu DOM Tree. Developer tingkat lanjut memahami bahwa browser engine (Blink, Gecko, WebKit) mengompilasi dua pohon utama secara paralel:
* **DOM Tree + CSSOM Tree $\rightarrow$ Render Tree** (untuk representasi visual pada piksel layar).
* **DOM Tree $\rightarrow$ Accessibility Tree (AOM/AXTree)** (untuk konsumsi oleh assistive technology/AT melalui OS Accessibility APIs).

Aksesibilitas bukanlah lapisan estetika visual tambahan; ia adalah representasi data paralel struktural dari antarmuka pengguna Anda.

```
+--------------------------------------------------------+
|                      HTML Markup                       |
+--------------------------------------------------------+
                           |
                           v
           +-------------------------------+
           |    Document Object Model      |
           +-------------------------------+
              /                         \
             v                           v
   +-------------------+       +--------------------+
   |   Render Tree     |       | Accessibility Tree |
   |  (Pixels, Canvas) |       |  (Roles, States)   |
   +-------------------+       +--------------------+
             |                           |
             v                           v
     Visual Monitor            Platform Accessibility
                                APIs (MSAA, UIA, AX)
                                         |
                                         v
                              Screen Readers / Braille
```

### 2. Aturan Pertama ARIA (First Rule of ARIA Use)
> *"Jika Anda dapat menggunakan elemen HTML semantik bawaan dengan fitur atau perilaku yang sudah Anda butuhkan, daripada mengubah peran suatu elemen menggunakan ARIA, lakukanlah."*

ARIA tidak menyuntikkan fungsionalitas keyboard bawaan, ARIA tidak menangani event fokus, dan ARIA tidak memodifikasi gaya rendering. ARIA **hanya** memperbarui data metadata (Name, Role, Value, State) pada Accessibility Tree untuk assistive technologies.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran data end-to-end yang mengilustrasikan bagaimana manipulasi DOM HTML dan atribut WAI-ARIA diterjemahkan menjadi perintah suara pada Screen Reader:

```
+------------------+      +-------------------+      +----------------------+
|  HTML5 Semantics | ---> | Blink/Gecko/WebKit| ---> |  Accessibility Tree  |
|   + WAI-ARIA     |      |    Core Engine    |      | (Roles/Names/States) |
+------------------+      +-------------------+      +----------------------+
                                                                |
                                                                v
+------------------+      +-------------------+      +----------------------+
| Screen Reader    | <--- | OS A11y Layer     | <--- | Platform APIs        |
| (VoiceOver/NVDA) |      | (IPC Messaging)   |      | (Mac AXUIElement /   |
| Audio Synthesis  |      |                   |      |  Win UI Automation)  |
+------------------+      +-------------------+      +----------------------+
```

### Keyboard Trapping & Focus Loop Execution Flow

```
          [User Presses 'TAB' Key]
                     |
                     v
      +------------------------------+
      | Target = Event.target        |
      | Trap Active?                 |
      +------------------------------+
            |                  |
           YES                 NO
            |                  |
            v                  +------------------> [Normal Browser Traversal]
+---------------------------------------+
| Is Shift Pressed? (Reverse Navigation)|
+---------------------------------------+
         |                     |
        YES                    NO
         |                     |
         v                     v
+------------------+   +-------------------+
| At First Node?   |   | At Last Node?     |
+------------------+   +-------------------+
    |         |            |          |
   YES        NO          YES         NO
    |         |            |          |
    v         v            v          v
[Focus    [Focus      [Focus      [Focus
 Last]     Prev]       First]      Next]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Simpul Accessibility Tree (AXNode)
Setiap simpul pada Accessibility Tree memiliki 4 komponen fundamental:

1. **Role**: Menentukan jenis elemen (contoh: `button`, `dialog`, `heading`, `checkbox`).
2. **Name (Accessible Name)**: Label identitas simpul (contoh: teks "Kirim Data" pada sebuah tombol). Dikalkulasikan melalui *Accessible Name and Description Computation Algorithm*.
3. **Description (Accessible Description)**: Informasi sekunder opsional, biasanya dipetakan via `aria-describedby`.
4. **State / Value**: Status interaktif saat ini (contoh: `expanded="true"`, `checked="mixed"`, `disabled`, `valuenow="50"`).

### 2. Algoritma Kalkulasi Accessible Name
Browser mengevaluasi Accessible Name dari sebuah simpul dengan urutan preseden ketat:
1. `aria-labelledby`: Mengambil teks dari elemen lain yang dirujuk oleh ID (preseden tertinggi).
2. `aria-label`: String eksplisit yang langsung disematkan pada elemen.
3. Label semantik natif: Elemen `<label for="...">` pada input form, atau atribut `alt` pada `<img>`.
4. Konten sub-pohon DOM (*Subtree text content*): Teks mentah di dalam elemen (misal: `<button>Simpan</button>`).
5. Atribut fallback: Atribut `title` (preseden terendah, sangat tidak disarankan sebagai sumber utama).

### 3. Jembatan API Aksesibilitas OS (OS Accessibility API Mapping)
Browser tidak berkomunikasi langsung dengan software screen reader. Browser memetakan AXNode ke API sistem operasi:
* **macOS / iOS**: NSAccessibility Protocol / AXUIElement.
* **Windows**: Microsoft UI Automation (UIA) & IAccessible2 (IA2).
* **Linux**: Assistive Technology Service Provider Interface (AT-SPI).
* **Android**: AccessibilityNodeInfo.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Taksonomi WAI-ARIA
WAI-ARIA (Web Accessibility Initiative - Accessible Rich Internet Applications) dibagi menjadi:
* **Roles**: 
  * *Landmark Roles*: Memberi navigasi makro (`main`, `navigation`, `banner`, `contentinfo`, `complementary`).
  * *Document Structure*: Mengidentifikasi blok konten non-interaktif (`article`, `list`, `table`).
  * *Widget Roles*: Komponen interaktif (`button`, `slider`, `dialog`, `tab`, `tabpanel`).
* **Live Regions**: Mekanisme untuk mengumumkan pembaruan konten dinamis tanpa memerlukan perpindahan fokus (`aria-live="polite"`, `aria-live="assertive"`).

### 2. Mekanisme Atribut Tabindex
Properti HTML `tabindex` mengatur siklus navigasi keyboard:
* `tabindex="0"`: Memasukkan elemen non-interaktif ke dalam urutan tab alami (fokus berurutan) dan membuatnya dapat menerima fokus programatik (`element.focus()`).
* `tabindex="-1"`: Menghapus elemen dari urutan tab alami, namun **tetap memungkinkan** elemen menerima fokus programatik via JavaScript.
* `tabindex="1+"` (Positif): **Anti-pattern mutlak**. Mengacaukan urutan fokus global dengan memaksa prioritas di atas urutan DOM alami.

### 3. Kontras Warna Matematis (WCAG 2.2 Relative Luminance)
Kontras dihitung berdasarkan rumus rasio kontras relatif:

$$CR = \frac{L_1 + 0.05}{L_2 + 0.05}$$

Di mana $L_1$ adalah luminansi relatif dari warna yang lebih terang, dan $L_2$ adalah luminansi warna yang lebih gelap. Nilai luminansi $L$ didefinisikan dari ruang warna sRGB ternormalisasi:

$$L = 0.2126 \times R + 0.7152 \times G + 0.0722 \times B$$

Komponen warna ternormalisasi $C \in \{R, G, B\}$ dikonversi dari rentang $[0, 1]$:
* Jika $C_{srgb} \leq 0.04045 \implies C = \frac{C_{srgb}}{12.92}$
* Jika $C_{srgb} > 0.04045 \implies C = \left(\frac{C_{srgb} + 0.055}{1.055}\right)^{2.4}$

* **Tingkat AA**: Rasio minimal **4.5:1** untuk teks normal (< 18pt regular atau < 14pt bold), dan **3.0:1** untuk teks besar serta komponen visual UI.
* **Tingkat AAA**: Rasio minimal **7.0:1** untuk teks normal, dan **4.5:1** untuk teks besar.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi murni pola **Accessible Disclosure (Accordion/Collapsible)** yang memenuhi kepatuhan WAI-ARIA 1.2 tanpa dependensi framework.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Accessible Disclosure Component</title>
  <style>
    .disclosure-btn {
      display: flex;
      justify-content: space-between;
      width: 100%;
      max-width: 400px;
      padding: 12px 16px;
      font-size: 1rem;
      font-weight: 600;
      background: #f1f5f9;
      border: 2px solid #cbd5e1;
      border-radius: 6px;
      cursor: pointer;
      text-align: left;
    }
    .disclosure-btn:focus-visible {
      outline: 3px solid #0284c7;
      outline-offset: 2px;
    }
    .disclosure-panel {
      max-width: 400px;
      padding: 16px;
      border: 1px solid #e2e8f0;
      border-top: none;
      border-radius: 0 0 6px 6px;
    }
    .disclosure-panel[hidden] {
      display: none;
    }
    .icon {
      transition: transform 0.2s ease-in-out;
    }
    .disclosure-btn[aria-expanded="true"] .icon {
      transform: rotate(180deg);
    }
  </style>
</head>
<body>

  <!-- Accessible Disclosure Pattern -->
  <div class="disclosure-widget">
    <h3>
      <button 
        type="button" 
        id="disclosure-trigger-1" 
        class="disclosure-btn"
        aria-expanded="false" 
        aria-controls="disclosure-content-1">
        <span>Detail Lisensi Komersial</span>
        <span class="icon" aria-hidden="true">&#9662;</span>
      </button>
    </h3>
    <div 
      id="disclosure-content-1" 
      class="disclosure-panel" 
      role="region" 
      aria-labelledby="disclosure-trigger-1"
      hidden>
      <p>Lisensi ini mencakup hak cipta penuh untuk penggunaan produksi skala enterprise.</p>
    </div>
  </div>

  <script>
    const trigger = document.getElementById('disclosure-trigger-1');
    const content = document.getElementById('disclosure-content-1');

    trigger.addEventListener('click', () => {
      const isExpanded = trigger.getAttribute('aria-expanded') === 'true';
      
      // Sinkronisasi status state ke DOM dan ARIA
      trigger.setAttribute('aria-expanded', String(!isExpanded));
      content.hidden = isExpanded;
    });

    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && trigger.getAttribute('aria-expanded') === 'true') {
        trigger.setAttribute('aria-expanded', 'false');
        content.hidden = true;
      }
    });
  </script>
</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 46 (`<h3>`)**: Elemen pembungkus menggunakan heading semantik. Ini memungkinkan pengguna screen reader melompati struktur dokumen dengan tombol pintas cepat (*heading navigation* / kunci `H`).
* **Baris 47-52 (`<button type="button" ...>`)**:
  * Menggunakan elemen semantik `<button>` untuk mendapatkan native keyboard triggers (`Enter` dan `Space`) secara otomatis tanpa javascript `keydown` tambahan.
  * Atribut `aria-expanded="false"`: Memberitahu AT bahwa panel yang dikontrol tombol ini sedang dalam status tertutup (*collapsed*).
  * Atribut `aria-controls="disclosure-content-1"`: Membentuk relasi programatik eksplisit dari tombol ke panel target menggunakan `id`.
* **Baris 53 (`aria-hidden="true"`)**: Menyembunyikan simbol visual panah (`▼`) dari pohon aksesibilitas. Jika tidak disembunyikan, screen reader akan membacakan glif grafis yang tidak perlu, menghasilkan noise vokal.
* **Baris 57-61 (`<div ... role="region" aria-labelledby="disclosure-trigger-1" hidden>`)**:
  * `hidden`: Atribut boolean standar HTML. Elemen dengan atribut ini sepenuhnya dihilangkan dari Render Tree dan Accessibility Tree.
  * `role="region"`: Menetapkan panel sebagai landmark mandiri.
  * `aria-labelledby`: Mengunci relasi dua arah agar nama region diambil secara langsung dari label teks tombol pemicu.
* **Baris 67-73 (`JavaScript Event Handlers`)**:
  * Melakukan toggle boolean state string `"true"` dan `"false"`. Menggunakan tipe data primitif string karena nilai atribut HTML ARIA selalu dievaluasi sebagai representasi string literal.
  * Penanganan tombol `Escape`: Menyediakan jalan keluar darurat keyboard yang menutup panel tanpa menghancurkan fokus.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Skenario Masalah
Sebuah platform perbankan digital skala enterprise meluncurkan modul verifikasi transfer multi-faktor berbentuk Modal Dialog. Tim audit kepatuhan menemukan kegagalan kritis pada standar WCAG 2.2 Level AA:
1. **Focus Leakage**: Ketika modal terbuka, pengguna keyboard dapat menekan tombol `Tab` dan memindahkan fokus visual ke formulir transfer di latar belakang (DOM background), memicu kerentanan salah transfer (*unintended submit*).
2. **Virtual Keyboard Blindness**: Pengguna screen reader kehilangan konteks ketika modal muncul; screen reader tidak mengumumkan bahwa jendela modal telah aktif, dan tetap membaca dokumen utama.
3. **Focus Loss on Dismiss**: Ketika modal ditutup, fokus browser ter-reset ke elemen `<body>`, memaksa pengguna disabilitas motorik mengulang penekanan tombol `Tab` puluhan kali dari awal halaman.

### Persyaratan Arsitektural Solusi
* Komponen Modal Dialog harus mengisolasi fokus sepenuhnya di dalam batasannya (*Focus Trap*).
* Modal harus merender `role="dialog"`, `aria-modal="true"`, serta mengumumkan judul secara eksplisit via `aria-labelledby`.
* Saat dibuka, fokus harus diarahkan ke elemen interaktif pertama yang valid di dalam modal.
* Saat ditutup (baik via tombol batal, tombol silang, atau tombol `Escape`), fokus keyboard harus dikembalikan secara deterministik ke elemen pemicu (*invoker*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem produksi kelas enterprise untuk Accessible Modal Dialog dengan Focus Trapping Native:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Accessible Modal Trap</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.5;
      padding: 2rem;
    }
    .backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.75);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }
    .backdrop[hidden] {
      display: none;
    }
    .modal-surface {
      background: #ffffff;
      border-radius: 8px;
      padding: 24px;
      width: 100%;
      max-width: 500px;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 24px;
    }
    :focus-visible {
      outline: 3px solid #2563eb;
      outline-offset: 2px;
    }
  </style>
</head>
<body>

  <!-- Halaman Utama (Main Context) -->
  <main id="app-root">
    <h1>Dashboard Transaksi Finansial</h1>
    <p>Silakan konfirmasi transaksi pembayaran tagihan Anda di bawah ini.</p>
    <button type="button" id="open-modal-trigger" class="btn-primary">
      Otorisasi Pembayaran (ID: #TRX-99482)
    </button>
  </main>

  <!-- Accessible Modal Container -->
  <div id="modal-backdrop" class="backdrop" hidden>
    <div 
      id="auth-modal" 
      class="modal-surface" 
      role="dialog" 
      aria-modal="true" 
      aria-labelledby="modal-title-node" 
      aria-describedby="modal-desc-node">
      
      <div class="modal-header">
        <h2 id="modal-title-node" style="margin: 0; font-size: 1.25rem;">Otorisasi Transaksi</h2>
        <button type="button" id="modal-close-icon" aria-label="Tutup jendela otorisasi">&times;</button>
      </div>

      <div class="modal-body">
        <p id="modal-desc-node">
          Anda akan melakukan transfer dana sebesar <strong>Rp 25.000.000</strong> ke Rekening Vendor Utama. Aksi ini tidak dapat dibatalkan.
        </p>
        <label for="otp-input" style="display: block; margin-top: 12px; font-weight: 500;">
          Masukkan Token 6-Digit:
        </label>
        <input 
          type="text" 
          id="otp-input" 
          maxlength="6" 
          autocomplete="one-time-code" 
          style="width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box;"
        />
      </div>

      <div class="modal-actions">
        <button type="button" id="modal-cancel-btn">Batalkan</button>
        <button type="button" id="modal-confirm-btn" style="background: #dc2626; color: #fff; border: none; padding: 8px 16px; border-radius: 4px;">
          Konfirmasi & Eksekusi
        </button>
      </div>
    </div>
  </div>

  <script>
    class AccessibleModalController {
      constructor(backdropId, modalId, appRootId) {
        this.backdrop = document.getElementById(backdropId);
        this.modal = document.getElementById(modalId);
        this.appRoot = document.getElementById(appRootId);
        this.previouslyFocusedElement = null;
        
        // CSS Selector untuk seluruh elemen yang berpotensi menerima fokus
        this.focusableElementsSelector = [
          'a[href]',
          'area[href]',
          'input:not([disabled])',
          'select:not([disabled])',
          'textarea:not([disabled])',
          'button:not([disabled])',
          'iframe',
          'object',
          'embed',
          '[tabindex]:not([tabindex="-1"])',
          '[contenteditable]'
        ].join(',');

        this.handleKeyDown = this.handleKeyDown.bind(this);
      }

      open(triggerElement) {
        this.previouslyFocusedElement = triggerElement;
        
        // Sembunyikan pohon aplikasi dari AT
        this.appRoot.setAttribute('aria-hidden', 'true');
        this.backdrop.hidden = false;

        document.addEventListener('keydown', this.handleKeyDown);

        // Alihkan fokus ke input utama di dalam modal secara aman
        const initialFocusNode = this.modal.querySelector('#otp-input') || this.getFocusableNodes()[0];
        if (initialFocusNode) {
          initialFocusNode.focus();
        }
      }

      close() {
        this.backdrop.hidden = true;
        this.appRoot.removeAttribute('aria-hidden');
        document.removeEventListener('keydown', this.handleKeyDown);

        // Restorasi fokus kembali ke pemanggil awal
        if (this.previouslyFocusedElement && typeof this.previouslyFocusedElement.focus === 'function') {
          this.previouslyFocusedElement.focus();
        }
      }

      getFocusableNodes() {
        const nodes = Array.from(this.modal.querySelectorAll(this.focusableElementsSelector));
        // Filter elemen yang disembunyikan via CSS (display: none / visibility: hidden)
        return nodes.filter(node => node.offsetWidth > 0 || node.offsetHeight > 0 || node.getClientRects().length > 0);
      }

      handleKeyDown(event) {
        if (event.key === 'Escape') {
          event.preventDefault();
          this.close();
          return;
        }

        if (event.key === 'Tab') {
          const focusableNodes = this.getFocusableNodes();
          if (focusableNodes.length === 0) {
            event.preventDefault();
            return;
          }

          const firstNode = focusableNodes[0];
          const lastNode = focusableNodes[focusableNodes.length - 1];

          if (event.shiftKey) {
            // Mundur (Shift + Tab)
            if (document.activeElement === firstNode) {
              event.preventDefault();
              lastNode.focus();
            }
          } else {
            // Maju (Tab)
            if (document.activeElement === lastNode) {
              event.preventDefault();
              firstNode.focus();
            }
          }
        }
      }
    }

    // Instansiasi dan Pengikatan Event
    const modalController = new AccessibleModalController('modal-backdrop', 'auth-modal', 'app-root');
    const openBtn = document.getElementById('open-modal-trigger');
    const closeBtn = document.getElementById('modal-close-icon');
    const cancelBtn = document.getElementById('modal-cancel-btn');
    const confirmBtn = document.getElementById('modal-confirm-btn');

    openBtn.addEventListener('click', () => modalController.open(openBtn));
    closeBtn.addEventListener('click', () => modalController.close());
    cancelBtn.addEventListener('click', () => modalController.close());
    
    confirmBtn.addEventListener('click', () => {
      alert('Transaksi berhasil diproses!');
      modalController.close();
    });
  </script>
</body>
</html>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

### Native HTML `<dialog>` vs Custom WAI-ARIA Modal Pattern

| Karakteristik | Native `<dialog>` Element | Custom ARIA Modal (`role="dialog"`) |
| :--- | :--- | :--- |
| **Top Layer Rendering** | Ya, otomatis menggunakan pseudo-elemen `::backdrop` dan native top layer (kebal terhadap `z-index` stacking context traps). | Tidak, bergantung pada struktur DOM penempatan dan hierarki manual CSS `z-index`. |
| **Focus Trapping** | Native melalui API method `.showModal()`. | Wajib dikalkulasi dan diikat secara manual via JavaScript Keyboard Event Listeners. |
| **Inertness Latar Belakang** | Otomatis membuat seluruh elemen saudara di luar dialog menjadi non-interaktif (*inert*). | Membutuhkan polyfill manual atau atribut `inert` / `aria-hidden="true"` pada container saudara. |
| **Dukungan Legacy Browser** | Butuh engine modern (Chrome 37+, Firefox 98+, Safari 15.4+). Butuh polyfill untuk browser lama. | Kompatibel dengan semua arsitektur browser legacy hingga IE11. |
| **Custom Animation Overhead**| Membutuhkan konfigurasi `@starting-style` CSS modern untuk menganimasikan *entry* dan *exit*. | Sangat fleksibel dikontrol langsung melalui transisi CSS tradisional. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Dynamic Subtree Injection & Focus Trap Race Condition
Jika isi modal memuat elemen via asynchronous fetching (AJAX/Fetch) setelah modal ditampilkan, daftar node yang dapat difokuskan (`focusableNodes`) akan berubah. Jika array tersebut di-cache di memori, fokus trap akan bocor atau melompat secara acak.
* **Mitigasi**: Jalankan kueri DOM dinamis di dalam *event loop Tab keydown* atau pantau subtree menggunakan `MutationObserver`.

### 2. Atribut `inert` Browser Support
Atribut modern HTML `inert` menonaktifkan seluruh interaksi dan parsing AT untuk suatu sub-pohon DOM.
```html
<main inert> <!-- Seluruh anak elemen otomatis unclickable, unfocusable, dan invisible bagi AT -->
```
* **Pitfall**: Jika Anda lupa menghapus `inert` saat modal ditutup, aplikasi Anda akan mengalami *deadlock* fungsional di mana pengguna tidak dapat mengklik apa pun.

### 3. Screen Reader "Virtual Cursor" vs Browser Focus
Pada screen reader desktop (NVDA/JAWS), tombol panah mengontrol *virtual buffer cursor*, bukan fokus DOM native. 
* **Pitfall**: Memberikan atribut `role="application"` untuk mengatasi hal ini dapat menonaktifkan seluruh tombol pintas bawaan pengguna AT dan merusak pengalaman navigasi. Jangan gunakan `role="application"` kecuali Anda sedang membangun spreadsheet kompleks sekelas Google Sheets.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menggunakan `aria-hidden="true"` pada Elemen yang Menerima Fokus
```html
<!-- KESALAHAN FATAL -->
<button aria-hidden="true">Hapus Akun</button>
```
* **Dampak**: Tombol masih dapat diakses melalui tombol `Tab` keyboard. Namun, screen reader akan membisu total saat pengguna mendarat di atasnya. Pengguna tunanetra tidak tahu elemen apa yang sedang aktif.
* **Solusi**: Jangan sembunyikan elemen fokus dari pohon aksesibilitas. Jika elemen harus disembunyikan, gunakan atribut `hidden` atau `disabled`.

### Kesalahan Fatal 2: Tombol Berbentuk `<div>` Tanpa Penanganan Interaksi Keyboard
```html
<!-- KESALAHAN FATAL -->
<div class="btn" onclick="submit()">Kirim Data</div>
```
* **Dampak**: Elemen ini tidak bisa difokuskan melalui `Tab` dan mengabaikan penekanan tombol `Enter` serta `Space`.
* **Solusi**: Ganti dengan `<button type="button">Kirim Data</button>`.

### Kesalahan Fatal 3: Placeholder Dijadikan Satu-satunya Label Form
```html
<!-- KESALAHAN FATAL -->
<input type="text" placeholder="Masukkan Nomor Rekening">
```
* **Dampak**: Teks placeholder menghilang saat pengguna mengetik, kontras warnanya secara default gagal memenuhi WCAG AA (kurang dari 4.5:1), dan banyak screen reader mengabaikan pembacaan placeholder.
* **Solusi**: Sertakan `<label for="acc-num">Nomor Rekening</label>`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Implementasikan Skip Links (Bypass Blocks - WCAG 2.4.1)**:
   Sediakan tautan tersembunyi sebagai simpul pertama pada `<body>` untuk memungkinkan pengguna keyboard melompati navigasi header yang berulang-ulang:
   ```html
   <a href="#main-content" class="skip-link">Lompat ke Konten Utama</a>
   ```
   ```css
   .skip-link {
     position: absolute;
     top: -9999px;
     left: -9999px;
   }
   .skip-link:focus {
     top: 10px;
     left: 10px;
     z-index: 99999;
     background: #000;
     color: #fff;
     padding: 8px 16px;
   }
   ```
2. **Jangan Pernah Menghilangkan Focus Ring Tanpa Pengganti (`outline: none`)**:
   Jika Anda menghapus outline visual default, Anda wajib menyediakan indikator `:focus-visible` alternatif dengan rasio kontras minimal 3:1 terhadap warna latar belakang.
3. **Penamaan Tombol Ikon (Icon-only Buttons)**:
   Selalu sematkan `aria-label` yang jelas pada tombol interaktif yang hanya menampilkan ikon grafis SVG atau glif font:
   ```html
   <button type="button" aria-label="Cari data dokumen">
     <svg aria-hidden="true" focusable="false"><!-- Icon --></svg>
   </button>
   ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

Meskipun WAI-ARIA beroperasi di level pohon semantik, integrasi yang ceroboh dapat menurunkan kinerja runtime browser:

1. **Throttling Live Region DOM Mutations**:
   Mengubah simpul pada elemen dengan atribut `aria-live="polite"` secara berulang dalam frekuensi tinggi (misalnya: logging pesan streaming per milidetik) memaksa sistem operasi membroadcast event IPC ke background process screen reader. Hal ini menyebabkan lag vokal parah dan membebani UI thread browser.
   * **Optimasi**: Terapkan *debounce* atau *throttle* pada pembaruan teks `aria-live` (minimal jeda 250ms–500ms).

2. **Menghindari Kueri DOM Berulang pada Keyboard Event Handlers**:
   Pada algoritma Focus Trap, jangan memanggil `document.querySelectorAll('*')` secara naif setiap kali tombol `Tab` ditekan. Simpan daftar elemen interaktif (*cache node collection*) dan hanya kalkulasi ulang saat terjadi mutasi struktural.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **DOM Clobbering Melalui Resolusi ID ARIA**:
   Atribut ARIA seperti `aria-labelledby` dan `aria-describedby` merujuk ke elemen melalui identifier string ID. Waspadai serangan *DOM Clobbering* di mana input pengguna yang tidak ter-sanitasi menyuntikkan ID yang sama dengan kontrol aksesibilitas sistem.
   * **Mitigasi**: Gunakan ID unik yang dienkapsulasi menggunakan `crypto.randomUUID()` untuk mengikat relasi ARIA dinamis:
   ```javascript
   const uniqueId = `uid-${crypto.randomUUID()}`;
   trigger.setAttribute('aria-controls', uniqueId);
   panel.setAttribute('id', uniqueId);
   ```
2. **Tabnabbing pada Tautan Eksternal**:
   Ketika menyediakan tautan eksternal bagi pengguna disabilitas, pastikan Anda menggunakan:
   ```html
   <a href="https://external.example.com" target="_blank" rel="noopener noreferrer">
     Dokumentasi Eksternal <span class="sr-only">(buka di tab baru)</span>
   </a>
   ```
   Teks bantuan tersembunyi (`sr-only`) memastikan pengguna tunanetra tidak bingung saat aplikasi membuka konteks window baru di luar aplikasi.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### 1. Mengakses Internal Accessibility Tree pada DevTools
* **Google Chrome / Microsoft Edge**: Buka DevTools (`F12`) $\rightarrow$ Tab **Elements** $\rightarrow$ Pilih panel samping **Accessibility** $\rightarrow$ Aktifkan opsi **Enable full-page accessibility tree**.
* Anda dapat memeriksa atribut **Computed Name**, **Role**, dan rantai inheritance kalkulasi label