# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Aksesibilitas Web Mendalam dan Integrasi WAI-ARIA**  
**Topik: HTML (Kategori: 03-Frontend-and-Mobile)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Browser Engine**: Menguraikan proses transformasi DOM dan CSSOM menjadi Platform Accessibility Tree (AXTree) lintas browser engine (Blink, Gecko, WebKit) dan platform APIs (UI Automation, IAccessible2, NSAccessibility, ATK).
2. **Merancang Komponen WAI-ARIA Kompleks**: Mengembangkan widget interaktif tingkat lanjut (Combobox 1.2, Modal Focus-Trap, Virtualized Grid) sesuai spesifikasi *WAI-ARIA Authoring Practices Guide (APG)* tanpa degradasi performa.
3. **Mengimplementasikan Manajemen Fokus Lanjut**: Membandingkan dan mengeksekusi arsitektur *Roving Tabindex* vs. `aria-activedescendant` pada dataset besar berkemampuan navigasi keyboard dua dimensi (2D).
4. **Membangun Sistem Live Notification Real-time**: Mengarsitekturi *Polite/Assertive Live Announcer* terpusat untuk memitigasi tabrakan pembacaan buffer pada Assistive Technology (AT) dalam aplikasi *real-time streaming*.
5. **Mengintegrasikan Automated Accessibility Testing**: Menyusun *pipeline* CI/CD berbasis `@axe-core/playwright` dengan zero-false-positive thresholding untuk level kepatuhan WCAG 2.2 Level AA.

---

## 2. Prerequisite

Peserta wajib menguasai:
* Pemahaman fundamental HTML5 Semantics dan WCAG 2.1 prinsip POUR (*Perceivable, Operable, Understandable, Robust*).
* Ekosistem DOM API tingkat lanjut: MutationObserver, NodeFilter, TreeWalker, dan Event Dispatching/Bubbling.
* Modern JavaScript / TypeScript (ES2022+): Pengelolaan memori, class abstraction, custom event interfaces.
* Pemahaman dasar penggunaan *Screen Readers* dasar (macOS VoiceOver, NVDA di Windows, atau Orca di Linux).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Siklus Hidup Aksesibilitas: DOM/CSSOM ke Platform Accessibility Tree

Aksesibilitas web modern bekerja melalui abstraksi paralel di dalam mesin peramban. Browser tidak secara langsung mengekspos DOM tree ke *Assistive Technologies* (seperti screen reader atau voice navigation software). Sebagai gantinya, browser mengompilasi representasi struktural khusus yang disebut **Accessibility Tree (AXTree)**.

```
+-----------------------------------------------------------------------+
|                            BROWSER ENGINE                             |
|                                                                       |
|  HTML Parsing --------> DOM Tree  \                                   |
|                                    +--> Render Tree -> AXTree Cache   |
|  CSS Parsing  --------> CSSOM Tree /                        |         |
|                                                             v         |
|                                                  Accessibility Tree   |
+-------------------------------------------------------------|---------+
                                                              |
                                           Platform Bridge/Adapter Layer
                                                              |
          +-------------------+-------------------------------+-------------------+
          |                   |                               |                   |
          v                   v                               v                   v
      [Windows]            [macOS]                         [Linux]            [Android]
     UI Automation    NSAccessibility                 ATK / AT-SPI2         Accessibility
    / IAccessible2                                                            Node Info
          |                   |                               |                   |
          v                   v                               v                   v
     NVDA / JAWS          VoiceOver                         Orca              TalkBack
```

#### Pipeline Komputasi AXTree:
1. **DOM Tree Mutasi**: Setiap mutasi tag HTML (penambahan node, modifikasi atribut) memicu rekalkulasi tree.
2. **Style Resolution (CSSOM)**: Sifat visual CSS secara radikal dapat memusnahkan atau memodifikasi node di dalam AXTree. Sebagai contoh:
   * `display: none` atau `visibility: hidden`: Node dan seluruh sub-pohonnya **dihapus secara total** dari AXTree.
   * `opacity: 0`: Node **tetap berada** di dalam AXTree (dapat dibaca oleh screen reader dan dapat menerima fokus keyboard), meskipun tidak tampak di layar secara visual.
   * Pseudo-elements (`::before`, `::after`): Konten berbasis CSS `content: "..."` disintesis langsung ke dalam AXTree sebagai text node turunan.
3. **Penyusunan Node Accessibility**: Setiap node AXTree merefleksikan 4 atribut fundamental:
   * **Role**: Klasifikasi elemen (misal: `button`, `heading`, `dialog`).
   * **Name**: Label terkomputasi berdasarkan *Accessible Name and Description Computation (AccName) 1.2*.
   * **State**: Kondisi dinamis (misal: `expanded`, `collapsed`, `checked`, `disabled`).
   * **Value**: Nilai metrik (misal: range slider `valuenow=50`).
4. **Bridge OS Native**: Browser engine memetakan model internal AXTree ke API native sistem operasi:
   * Windows: Microsoft UI Automation (UIA) / IAccessible2 (IA2).
   * macOS: NSAccessibility / AXUIElement.
   * Linux: ATK (Accessibility Toolkit) / AT-SPI2.
   * Android: AccessibilityNodeInfo.

### 3.2 AccName Algorithm Internals (Accessible Name Computation)

Komputasi nama aksesibel mematuhi preseden berurutan yang kaku. Kegagalan memahami prioritas ini memicu bug pelabelan hantu (*label shadowing*):

$$\text{Prioritas AccName}: \text{aria-labelledby} > \text{aria-label} > \text{Host Language Semantics (native label)} > \text{aria-description/title}$$

1. Jika elemen memiliki `aria-labelledby`, browser memisahkan ID referensi dengan spasi, mengambil innerText terkomputasi dari masing-masing node referensi (rekursif), dan menghentikan pemrosesan atribut label lainnya.
2. Jika tidak ada `aria-labelledby`, browser membaca string mentah dari atribut `aria-label`.
3. Jika tidak ada atribut ARIA, browser mengevaluasi semantik native HTML:
   * Elemen `<input>`: Membaca teks `<label for="...">`, atau teks penutup `<label><input /></label>`.
   * Elemen `<img>`: Membaca atribut `alt`.
   * Elemen `<table>`: Membaca elemen `<caption>`.
4. Jika kosong, fallback fallback terakhir menggunakan `title` atau `placeholder` (anti-pattern jika placeholder digunakan sebagai label primer).

### 3.3 Roving Tabindex vs. `aria-activedescendant`

Navigasi keyboard dua dimensi (misal: grid data, menu drop-down, tree view) memerlukan pola khusus untuk mencegah jebakan navigasi Tab (mengurangi *tab-stops* berlebihan). Ada dua paradigma arsitektur untuk kasus ini:

| Parameter Evaluasi | Roving `tabindex` Pattern | `aria-activedescendant` Pattern |
| :--- | :--- | :--- |
| **Mekanisme Fokus DOM** | Menggeser `tabindex="0"` ke elemen aktif, mengubah sibling ke `tabindex="-1"`, lalu memanggil `element.focus()`. | Fokus DOM fisik **terkunci permanen** pada elemen pembungkus (container/input). Penunjuk bergeser via atribut pointer ID. |
| **Mutasi DOM** | Tinggi: Mengubah atribut `tabindex` secara terus menerus pada node anak setiap tombol panah ditekan. | Sangat Rendah: Hanya memutasi satu atribut pada container (`aria-activedescendant="item-id-active"`). |
| **Dukungan Virtualisasi** | Rumit: Node harus terikat di DOM fisik saat menerima native focus. | Sangat Baik: Ideal untuk Virtualized List, di mana child nodes di-mount/unmount secara dinamis saat digeser. |
| **Styling Dependency** | Mengandalkan CSS pseudo-class `:focus`. | Memerlukan class khusus (misal: `.is-selected`) karena elemen turunan tidak pernah menerima `:focus` native. |
| **Screen Reader Latency** | Lebih konsisten di seluruh browser engine lama. | Sangat responsif pada browser modern, tetapi membutuhkan sinkronisasi ID yang mutlak valid. |

---

## 4. Why & What

### Mengapa Aksesibilitas Tingkat Lanjut Bukan Sekadar "Best Practice"
1. **Regulasi dan Tanggung Jawab Hukum Global**: Penerapan European Accessibility Act (EAA) 2025 dan enforcement regulasi Title III ADA di AS memberlakukan denda finansial masif dan mitigasi penutupan layanan digital untuk platform B2B/B2C enterprise yang gagal memenuhi WCAG 2.1/2.2 level AA.
2. **Kualitas Arsitektur Rekayasa Perangkat Lunak**: Membangun aplikasi yang sepenuhnya aksesibel memaksa desentralisasi logika presentasi dari logika state, menghasilkan arsitektur headless yang lebih modular, *testable*, dan tahan terhadap refaktor UI.
3. **SEO dan Machine Readability**: Search Engine Crawlers (Googlebot) beroperasi sangat mirip dengan assistive technologies tanpa kapabilitas visual, memanfaatkan struktur semantik dan AXTree untuk mengekstrak entity graph data web application.

### Apa yang Salah dengan ARIA yang Diimplementasikan Sembarangan?
Aturan Pertama ARIA (*First Rule of ARIA*):
> *"Jika Anda bisa menggunakan elemen semantik HTML native dengan perilaku dan semantik yang sudah built-in, gunakan itu daripada memodifikasi elemen non-semantik dengan ARIA."*

Menambahkan `role="button"` pada sebuah `<div>` tidak mengubah div tersebut menjadi elemen yang otomatis dapat ditekan dengan `Enter`/`Space`, tidak menambahkan fokus default, dan tidak mengikutsertakannya dalam *form submission*. Penggunaan ARIA yang keliru justru menghasilkan disinformasi bagi pengguna alat bantu bantu (lebih berbahaya daripada ketiadaan ARIA sama sekali).

---

## 5. How (Workflow Detail)

Alur kerja rekayasa komponen interaktif kompleks ramah aksesibilitas (*Accessible Complex Widget Lifecycle*):

```
+-----------------------------------------------------------------------------------+
|                            FASE 1: SEMANTIC BASELINE                              |
| Tentukan apakah elemen native ada (<select>, <dialog>, <details>).                |
| Jika styling/requirement membatasi, definisikan Headless State Chart.             |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        FASE 2: ROLE & ACCNAME ANCHORING                           |
| Petakan container role & sub-roles (misal: role="combobox", role="listbox").      |
| Hubungkan relasi dinamis via `aria-controls`, `aria-owns`, dan `aria-expanded`.   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                       FASE 3: KEYBOARD INTERACTION MATRIX                         |
| Implementasikan state-machine untuk tombol: ArrowUp/Down, Home, End, Escape, Enter|
| Terapkan Focus Trap jika dialog modal terbuka, cegah scroll-bleed.                |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        FASE 4: LIVE ANNOUNCEMENT BUFFER                           |
| Tangani feedback dinamis (hasil pencarian, error async) via Live Region terpusat.  |
| Hindari saturasi screen reader queue dengan debouncing announcement.             |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         FASE 5: AUTOMATED & MANUAL AUDIT                          |
| 1. Unit testing a11y tree assertions via @axe-core.                               |
| 2. E2E navigasi keyboard tanpa mouse (Tab-order tracing).                         |
| 3. Verifikasi dengan screen reader aktif (VoiceOver / NVDA).                      |
+-----------------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Ruang Kontrol Kokpit Pesawat Modern
* **Visual UI (Layar Sentuh LCD)**: Menampilkan visual untuk pilot yang melihat layar. Jika pilot tidak dapat melihat layar visual, tombol-tombol fungsional harus memiliki respons haptik, bentuk mekanis unik, dan umpan balik suara.
* **Accessibility Tree (Sistem Audio & Flight Instrument Bus)**: Ini adalah interface analog/suara di kokpit. Ketika sistem hidrolik rusak, kokpit tidak sekadar mewarnai layar dengan warna merah (visual saja), melainkan memicu peringatan suara terprioritisasi ("*Warning: Hydraulic Pressure Low*") via speaker interkom (mirip `aria-live="assertive"`).

### Diagram Interaksi Combobox: Pergeseran Fokus & State Synchronization

```
User Action: Menekan Tombol [ ArrowDown ] pada Input Pencarian

               +----------------------------------------------------------+
               |                     HTML INPUT ELEMENT                   |
               |                                                          |
               |  <input role="combobox"                                  |
               |         aria-expanded="true"                             |
               |         aria-autocomplete="list"                         |
               |         aria-controls="listbox-options"                  |
               | [Focus] aria-activedescendant="opt-2" >                  |
               +----------------------------------------------------------+
                                           |
                    +----------------------+----------------------+
                    | (Penunjuk Relasi ID)                        | (Renders Child Nodes)
                    v                                             v
     +-------------------------------+             +------------------------------+
     |   AXTree Virtual Selection    |             |      HTML UL/LISTBOX ELEMENT |
     |                               |             |                              |
     |   Screen Reader mengumumkan:  |             |  <ul id="listbox-options"    |
     |   "Tokyo, Option 2 of 5"      |             |      role="listbox">         |
     +-------------------------------+             +------------------------------+
                                                                  |
                               +----------------------------------+----------------------------------+
                               |                                  |                                  |
                               v                                  v                                  v
                +------------------------------+   +------------------------------+   +------------------------------+
                | <li id="opt-1" role="option" |   | <li id="opt-2" role="option" |   | <li id="opt-3" role="option" |
                |     aria-selected="false">   |   |     aria-selected="true"     |   |     aria-selected="false">   |
                |   Jakarta                    |   |   Tokyo (Visual Highlight)   |   |   London                     |
                +------------------------------+   +------------------------------+   +------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Fully Accessible Custom Switch Toggle

Komponen switch murni native semantics tidak tersedia secara langsung dalam elemen HTML standar tanpa atribut input radio/checkbox. Berikut cara membangun custom switch menggunakan standar WAI-ARIA yang sepenuhnya taat spesifikasi.

```html
<!-- index.html -->
<div class="toggle-container">
  <span id="dark-mode-label" class="label-text">Mode Gelap Otomatis</span>
  <button 
    type="button" 
    role="switch" 
    id="dark-mode-toggle"
    aria-checked="false" 
    aria-labelledby="dark-mode-label"
    class="switch-control"
  >
    <span class="switch-handle" aria-hidden="true"></span>
  </button>
</div>

<style>
  .switch-control {
    width: 48px;
    height: 24px;
    background-color: #cbd5e1;
    border-radius: 9999px;
    border: 2px solid transparent;
    cursor: pointer;
    position: relative;
    outline: none;
    transition: background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .switch-control:focus-visible {
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.5);
    border-color: #2563eb;
  }

  .switch-control[aria-checked="true"] {
    background-color: #2563eb;
  }

  .switch-handle {
    display: block;
    width: 20px;
    height: 20px;
    background-color: #ffffff;
    border-radius: 50%;
    transform: translateX(0);
    transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .switch-control[aria-checked="true"] .switch-handle {
    transform: translateX(24px);
  }
</style>

<script>
  const toggleBtn = document.getElementById('dark-mode-toggle');
  
  toggleBtn.addEventListener('click', () => {
    const isChecked = toggleBtn.getAttribute('aria-checked') === 'true';
    toggleBtn.setAttribute('aria-checked', String(!isChecked));
  });

  // WAI-ARIA Switch Specification mewajibkan trigger spasi & enter natively di-handle oleh <button>,
  // namun jika menggunakan div (anti-pattern), kita wajib menyusun manual handler KeyboardEvent.
</script>
```

---

### 7.2 Practical Example: Enterprise-Grade Combobox 1.2 (Search & Select)

Komponen Combobox tingkat produksi ini mengimplementasikan:
1. Keyboard Navigation 1D menggunakan pola `aria-activedescendant`.
2. Dynamic Filtering tanpa merusak status pembacaan screen reader.
3. Accessible Error Announcing & State Control.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Accessible Enterprise Combobox</title>
  <style>
    .combobox-wrapper {
      position: relative;
      width: 320px;
      font-family: system-ui, -apple-system, sans-serif;
    }
    .combobox-label {
      display: block;
      font-weight: 600;
      margin-bottom: 6px;
      color: #1e293b;
    }
    .input-container {
      position: relative;
      display: flex;
    }
    .combobox-input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid #94a3b8;
      border-radius: 6px;
      font-size: 14px;
      outline: none;
    }
    .combobox-input:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
    }
    .combobox-listbox {
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      margin-top: 4px;
      padding: 0;
      list-style: none;
      max-height: 200px;
      overflow-y: auto;
      z-index: 10;
      box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
      display: none;
    }
    .combobox-listbox.is-open {
      display: block;
    }
    .combobox-option {
      padding: 10px 12px;
      cursor: pointer;
      font-size: 14px;
      color: #334155;
    }
    .combobox-option.is-active,
    .combobox-option:hover {
      background-color: #eff6ff;
      color: #1d4ed8;
      font-weight: 500;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border-width: 0;
    }
  </style>
</head>
<body>

  <div class="combobox-wrapper">
    <label id="cb-label" for="cb-input" class="combobox-label">Pilih Kantor Cabang Wilayah</label>
    <div class="input-container">
      <input
        id="cb-input"
        type="text"
        role="combobox"
        class="combobox-input"
        aria-autocomplete="list"
        aria-expanded="false"
        aria-haspopup="listbox"
        aria-controls="cb-listbox"
        aria-labelledby="cb-label"
        autocomplete="off"
        spellcheck="false"
      />
    </div>
    
    <ul
      id="cb-listbox"
      role="listbox"
      class="combobox-listbox"
      aria-labelledby="cb-label"
      tabindex="-1"
    ></ul>

    <!-- Dynamic Status Announcer Buffer -->
    <div id="cb-live-region" class="sr-only" aria-live="polite" aria-atomic="true"></div>
  </div>

  <script>
    class AccessibleCombobox {
      constructor(containerNode, options) {
        this.container = containerNode;
        this.options = options;
        this.filteredOptions = [...options];
        this.activeIndex = -1;
        this.isOpen = false;

        this.input = this.container.querySelector('[role="combobox"]');
        this.listbox = this.container.querySelector('[role="listbox"]');
        this.liveRegion = this.container.querySelector('[aria-live]');

        this.initEvents();
      }

      initEvents() {
        this.input.addEventListener('input', this.handleInput.bind(this));
        this.input.addEventListener('keydown', this.handleKeyDown.bind(this));
        this.input.addEventListener('blur', this.handleBlur.bind(this));
        this.listbox.addEventListener('mousedown', this.handleMouseDown.bind(this));
      }

      handleInput(event) {
        const query = this.input.value.toLowerCase().trim();
        this.filteredOptions = this.options.filter(item => 
          item.label.toLowerCase().includes(query)
        );
        this.activeIndex = -1;
        this.renderOptions();
        this.openDropdown();
        this.announceResults();
      }

      announceResults() {
        const count = this.filteredOptions.length;
        this.liveRegion.textContent = count > 0 
          ? `${count} opsi tersedia. Gunakan panah atas dan bawah untuk bernavigasi.`
          : 'Tidak ada hasil yang cocok.';
      }

      renderOptions() {
        this.listbox.innerHTML = '';
        if (this.filteredOptions.length === 0) {
          const emptyLi = document.createElement('li');
          emptyLi.className = 'combobox-option';
          emptyLi.textContent = 'Tidak ditemukan data';
          emptyLi.setAttribute('aria-disabled', 'true');
          this.listbox.appendChild(emptyLi);
          return;
        }

        this.filteredOptions.forEach((opt, idx) => {
          const li = document.createElement('li');
          li.id = `cb-opt-${opt.id}`;
          li.className = 'combobox-option';
          li.setAttribute('role', 'option');
          li.setAttribute('aria-selected', 'false');
          li.textContent = opt.label;
          this.listbox.appendChild(li);
        });
      }

      handleKeyDown(event) {
        const { key } = event;

        switch (key) {
          case 'ArrowDown':
            event.preventDefault();
            if (!this.isOpen) {
              this.openDropdown();
              this.setActiveIndex(0);
            } else {
              this.setActiveIndex(Math.min(this.activeIndex + 1, this.filteredOptions.length - 1));
            }
            break;

          case 'ArrowUp':
            event.preventDefault();
            if (this.isOpen) {
              this.setActiveIndex(Math.max(this.activeIndex - 1, 0));
            }
            break;

          case 'Enter':
            if (this.isOpen && this.activeIndex >= 0) {
              event.preventDefault();
              this.selectOption(this.filteredOptions[this.activeIndex]);
            }
            break;

          case 'Escape':
            if (this.isOpen) {
              event.preventDefault();
              this.closeDropdown();
              this.setActiveIndex(-1);
            }
            break;

          case 'Tab':
            this.closeDropdown();
            break;
        }
      }

      setActiveIndex(index) {
        this.activeIndex = index;
        const items = this.listbox.querySelectorAll('[role="option"]');
        
        items.forEach((item, idx) => {
          if (idx === index) {
            item.classList.add('is-active');
            item.setAttribute('aria-selected', 'true');
            this.input.setAttribute('aria-activedescendant', item.id);
            item.scrollIntoView({ block: 'nearest' });
          } else {
            item.classList.remove('is-active');
            item.setAttribute('aria-selected', 'false');
          }
        });

        if (index === -1) {
          this.input.removeAttribute('aria-activedescendant');
        }
      }

      selectOption(option) {
        this.input.value = option.label;
        this.closeDropdown();
        this.input.focus();
        this.liveRegion.textContent = `${option.label} terpilih.`;
      }

      openDropdown() {
        if (this.isOpen) return;
        this.isOpen = true;
        this.listbox.classList.add('is-open');
        this.input.setAttribute('aria-expanded', 'true');
        if (this.listbox.children.length === 0) {
          this.renderOptions();
        }
      }

      closeDropdown() {
        if (!this.isOpen) return;
        this.isOpen = false;
        this.listbox.classList.remove('is-open');
        this.input.setAttribute('aria-expanded', 'false');
        this.setActiveIndex(-1);
      }

      handleMouseDown(event) {
        const optionNode = event.target.closest('[role="option"]');
        if (!optionNode || optionNode.getAttribute('aria-disabled') === 'true') return;
        
        const optionId = optionNode.id.replace('cb-opt-', '');
        const selected = this.filteredOptions.find(o => String(o.id) === optionId);
        if (selected) {
          this.selectOption(selected);
        }
      }

      handleBlur() {
        // Berikan delay kecil untuk mengakomodasi eksekusi mousedown pada list
        setTimeout(() => {
          this.closeDropdown();
        }, 150);
      }
    }

    // Instansiasi
    const datasets = [
      { id: 'jkt', label: 'Jakarta Raya - Central Headquarter' },
      { id: 'sby', label: 'Surabaya - Jawa Timur Logistics Hub' },
      { id: 'bdg', label: 'Bandung - Engineering Center' },
      { id: 'mdn', label: 'Medan - Sumatera Operations' },
      { id: 'dps', label: 'Denpasar - Nusa Tenggara Outpost' }
    ];

    new AccessibleCombobox(document.querySelector('.combobox-wrapper'), datasets);
  </script>
</body>
</html>
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Platform Perdagangan Saham & Valuta Asing (Fintech Trading Terminal)
* **Skala Sistem**: Dashboard keuangan berbasis single-page application yang menerima pembaruan WebSockets hingga 120 *events* per detik berisi pergerakan harga saham, perubahan order-book, dan eksekusi transaksi.
* **Problem**: 
  1. Pengembang meletakkan `aria-live="assertive"` langsung di setiap baris tabel transaksi bursa saham.
  2. Hasilnya adalah *audio-buffer explosion* pada screen reader pengguna tuna netra. Screen reader membaca ribuan angka tanpa henti, memicu *input freeze* pada browser UI thread, dan membuat aplikasi tidak responsif.
  3. Navigasi keyboard pada data grid 10.000 entri menyebabkan lonjakan alokasi heap memori (memory leak) akibat penambahan event listener pada setiap tag `<tr>` dan `<td>`.

### Analisis Akar Masalah (Root Cause Failure)
1. **Misalignment Model Live Region**: `aria-live="assertive"` menginterupsi antrean audio native OS secara seketika. Pembaruan harga frekuensi tinggi tidak boleh diperlakukan sebagai interupsi kritikal sistem.
2. **Ketiadaan Throttle/Debounce Layer**: Screen reader memiliki kapasitas pemrosesan audio speech rate sebesar $\approx 250 - 400$ kata per menit. Mendorong 120 pesan per detik melanggar throughput fisiologis manusia dan sistem buffer speech synthesizer.
3. **DOM Pollution**: 10.000 elemen `tr` memiliki atribut `tabindex="0"`, menghancurkan *Accessibility Tree hierarchy caching*.

### Solusi Arsitektural Terapan
1. **Pemisahan Jalur Audio Melalui Dedicated Central Announcer Engine**:
   Membuat abstraksi `A11yTelemetryBroker` dengan mekanisme *Sliding-Window Batching*. Pembaruan harga hanya diumumkan secara agregat setiap 5 detik ke dalam buffer `aria-live="polite"` terisolasi, bukan per tick harga mikro.
2. **Pola Data Grid Berbasis Virtualisasi**:
   Hanya 25 baris yang terpasang di DOM fisik. Seluruh navigasi cell 2D menggunakan arsitektur `aria-activedescendant` pada parent `role="grid"`, memusnahkan kebutuhan memasang `tabindex` pada puluhan ribu cell fisik.
3. **Emergency Alert Channel**:
   `aria-live="assertive"` hanya dialokasikan khusus jika status order pengguna tereksekusi (*order fulfilled*) atau terjadi kegagalan koneksi sistem (*circuit breaker trip*).

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Konsekuensi Negatif | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Native Elements (`<dialog>`, `<select>`)** | Bebas konfigurasi ARIA, dukungan native keyboard focus, footprint JavaScript nol, teruji lintas AT. | Sangat kaku dalam kustomisasi tampilan CSS ekstrem lintas browser, render dialog backdrop memiliki quirk inkonsistensi rendering safari lama. | Form standar internal enterprise, portal admin, dokumen konten statis. |
| **Headless ARIA Pattern (Radix UI, Headless UI, Custom Engine)** | Kontrol UI styling 100% tanpa batasan native CSS engine, akses ke behavior kompleks (virtual list combobox). | Bundle size bertambah, overhead eksekusi JavaScript, risiko regresi aksessibilitas tinggi jika state machine cacat. | Consumer-facing products dengan standar branding tinggi (Fintech, Design System kompleks). |
| **ARIA Live: `assertive`** | Pesan langsung memotong dialog pembacaan AT seketika tanpa penundaan. | Menghapus antrean suara penting yang sedang didengarkan pengguna; berisiko menyebabkan disorientasi kognitif jika overused. | Hanya untuk sistem error fatal, sesi timeout perbankan dalam hitungan detik, kegagalan network kritis. |
| **ARIA Live: `polite`** | Menunggu pengguna selesai berinteraksi atau antrean audio saat ini kosong sebelum membaca pesan baru. | Pesan dinamis dapat tertunda beberapa detik jika ada aktivitas input berkelanjutan dari pengguna. | Feedback mutasi form, filter update, toast info, status simpan otomatis (*autosave*). |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Umum dalam Arsitektur Aksesibilitas
1. **Jebakan `aria-hidden="true"` pada Elemen Aktif**:
   ```html
   <!-- FATAL ERROR: Elemen dapat difokus tapi tidak terlihat oleh Screen Reader -->
   <button aria-hidden="true" onclick="openMenu()">Buka Menu</button>
   ```
   *Dampak*: Keyboard focus mendarat pada area "kosong" menurut AT. Screen reader terdiam membisu, pengguna tidak tahu elemen apa yang sedang aktif.

2. **Penggunaan Atribut Non-Eksisten atau Invalid State**:
   ```html
   <!-- SALAH -->
   <div role="button" aria-readonly="true">Submit</div> 
   <!-- Atribut aria-readonly tidak valid untuk role button menurut W3C WAI-ARIA Spec -->
   
   <!-- BENAR -->
   <button type="submit" disabled>Submit</button>
   ```

3. **Duplikasi Label (`aria-label` menimpa Teks Anak Secara Brutal)**:
   ```html
   <!-- BROWSER AKAN MENGABAIKAN KATA 'Hapus Akun Pengguna' -->
   <button aria-label="Tutup">Hapus Akun Pengguna</button>
   <!-- Pengguna AT akan mendengar 'Tutup', padahal tombol melakukan aksi destruktif 'Hapus Akun Pengguna' -->
   ```

4. **Kehilangan Fokus Saat Dialog Modal Ditutup**:
   Membuka modal memindahkan fokus ke dalam modal, namun ketika tombol "Batal" ditekan dan dialog di-unmount, fokus terlempar ke elemen `<body>`. Pengguna keyboard tuna netra harus menekan Tab ratusan kali untuk kembali ke posisi semula.

### Matriks Pemecahan Masalah (Troubleshooting Guide)

```
Masalah: Screen Reader tidak bersuara saat konten dinamis muncul via Fetch/AJAX.
├── 1. Periksa apakah elemen Live Region dimuat bersamaan dengan isinya?
│    └── YA: FATAL. Live Region HARUS sudah ada di DOM SEBELUM teks disuntikkan.
│         └── Solusi: Render container <div aria-live="polite"> saat inisialisasi aplikasi.
│
├── 2. Apakah konten diubah menggunakan `innerHTML = innerHTML`?
│    └── YA: DOM node identity musnah, AT membatalkan tracking mutasi.
│         └── Solusi: Gunakan node.textContent = "pesan baru".
│
└── 3. Apakah atribut aria-atomic diatur secara tepat?
     └── TIDAK: Browser hanya akan membaca delta teks kecil, bukan kalimat utuh.
          └── Solusi: Pasang aria-atomic="true" pada live container.
```

---

## 11. Best Practices (Production Checklist)

### Semantic & DOM Level
- [ ] Tidak ada interaksi fungsional click yang dipasang pada non-interactive tag (`<div>`, `<span>`) tanpa penambahan `role`, `tabindex="0"`, dan keyboard event handler (`Enter` dan `Space`).
- [ ] Aturan Pertama ARIA dipatuhi secara konsisten: Gunakan `<button>`, bukan `<div role="button">`.
- [ ] Atribut label (`aria-label` atau `aria-labelledby`) diaplikasikan pada semua tag form, tombol ikon saja (icon-only button), dan landmark navigation (`<nav aria-label="Utama">`).

### Focus Management & Keyboard UX
- [ ] Seluruh state visual `:focus-visible` memiliki rasio kontras minimum $3:1$ terhadap background di sekitarnya.
- [ ] Indikator fokus outline tidak pernah dihilangkan (`outline: none` atau `outline: 0`) tanpa penggantian styling visual fokus yang valid.
- [ ] Ketika sebuah Modal Dialog dibuka:
  - Fokus dipindahkan ke elemen pertama di dalam modal atau ke container modal itu sendiri.
  - Tab cycle terkunci (*Focus Trap*) di dalam dialog modal; tab tidak boleh melompat ke belakang modal.
  - Penekanan tombol `Escape` menutup modal dan mengembalikan fokus fisik tepat ke tombol pemicu (*trigger button*).

### Headless & WAI-ARIA
- [ ] Semua ID yang direferensikan dalam `aria-controls`, `aria-labelledby`, `aria-describedby`, dan `aria-activedescendant` benar-benar terdaftar di dalam DOM saat state aktif.
- [ ] Pola `aria-expanded` (true/false) terpasang pada semua kontrol toggle akordion, dropdown, dan menu navigasi.
- [ ] Status disabled menggunakan atribut HTML disabled native pada tag semantic; gunakan `aria-disabled="true"` hanya jika memerlukan fokus keyboard untuk keperluan membaca tooltip deskripsi error.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan berikut di direktori proyek lokal Anda: `hands-on/m02/`.

### Struktur File:
```
hands-on/m02/
├── index.html
├── style.css
├── src/
│   ├── FocusTrap.js
│   ├── Announcer.js
│   └── Modal.js
└── app.js
```

### Langkah 1: Siapkan Struktur Dokumen (`index.html`)
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Production Modal Focus Trap Architecture</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>

  <main id="main-content" class="content-wrapper">
    <h1>Dashboard Pengaturan Profil</h1>
    <p>Kelola konfigurasi data keamanan akun dan otentikasi dua faktor di sini.</p>
    
    <button id="open-modal-btn" class="btn-primary">
      Ubah Kata Sandi
    </button>
  </main>

  <!-- Centralized Accessibility Announcer Layer -->
  <div id="app-announcer" class="sr-only" aria-live="polite" aria-atomic="true"></div>

  <!-- Accessible Modal Layer -->
  <div id="modal-backdrop" class="modal-backdrop" hidden>
    <div 
      id="security-modal" 
      role="dialog" 
      aria-modal="true" 
      aria-labelledby="modal-title" 
      aria-describedby="modal-desc" 
      class="modal-window"
      tabindex="-1"
    >
      <header class="modal-header">
        <h2 id="modal-title">Perbarui Kata Sandi Anda</h2>
        <button id="close-modal-x" class="btn-close" aria-label="Tutup jendela dialog">&times;</button>
      </header>

      <div class="modal-body">
        <p id="modal-desc">Pastikan kata sandi baru mengandung minimal 12 karakter alfanumerik beserta simbol.</p>
        
        <form id="password-form">
          <div class="form-group">
            <label for="old-pass">Kata Sandi Saat Ini</label>
            <input type="password" id="old-pass" required class="form-input">
          </div>

          <div class="form-group">
            <label for="new-pass">Kata Sandi Baru</label>
            <input type="password" id="new-pass" required class="form-input">
          </div>

          <div class="modal-footer">
            <button type="button" id="cancel-btn" class="btn-secondary">Batalkan</button>
            <button type="submit" class="btn-primary">Simpan Perubahan</button>
          </div>
        </form>
      </div>
    </div>
  </div>

  <script type="module" src="app.js"></script>
</body>
</html>
```

### Langkah 2: Styling Aksesibel & Layer Tampilan (`style.css`)
```css
* {
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  margin: 0;
  padding: 40px;
  background-color: #f8fafc;
  color: #0f172a;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.content-wrapper {
  max-width: 600px;
  margin: 0 auto;
}

.btn-primary {
  background: #2563eb;
  color: white;
  border: none;
  padding: 10px 18px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.btn-secondary {
  background: #e2e8f0;
  color: #334155;
  border: none;
  padding: 10px 18px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.btn-primary:focus-visible,
.btn-secondary:focus-visible,
.form-input:focus-visible,
.btn-close:focus-visible {
  outline: 3px solid #f59e0b;
  outline-offset: 2px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-backdrop[hidden] {
  display: none;
}

.modal-window {
  background: white;
  border-radius: 8px;
  width: 100%;
  max-width: 480px;
  padding: 24px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
}

.form-group {
  margin-top: 16px;
}

.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 4px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
}

.modal-footer {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
```

### Langkah 3: Modul Focus Trap Engine (`src/FocusTrap.js`)
```javascript
export class FocusTrap {
  constructor(element) {
    this.rootNode = element;
    this.focusableSelector = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(', ');
    
    this.handleKeyDown = this.handleKeyDown.bind(this);
  }

  getFocusableNodes() {
    const nodes = Array.from(this.rootNode.querySelectorAll(this.focusableSelector));
    return nodes.filter(node => node.offsetParent !== null); // Hanya ambil yang terlihat
  }

  activate() {
    document.addEventListener('keydown', this.handleKeyDown);
  }

  deactivate() {
    document.removeEventListener('keydown', this.handleKeyDown);
  }

  handleKeyDown(event) {
    if (event.key !== 'Tab') return;

    const focusableNodes = this.getFocusableNodes();
    if (focusableNodes.length === 0) {
      event.preventDefault();
      return;
    }

    const firstNode = focusableNodes[0];
    const lastNode = focusableNodes[focusableNodes.length - 1];

    if (event.shiftKey) {
      // Navigasi mundur (Shift + Tab)
      if (document.activeElement === firstNode) {
        event.preventDefault();
        lastNode.focus();
      }
    } else {
      // Navigasi maju (Tab)
      if (document.activeElement === lastNode) {
        event.preventDefault();
        firstNode.focus();
      }
    }
  }
}
```

### Langkah 4: Modul Central Announcer Engine (`src/Announcer.js`)
```javascript
export class Announcer {
  constructor(announcerNodeId = 'app-announcer') {
    this.node = document.getElementById(announcerNodeId);
  }

  say(message, priority = 'polite') {
    if (!this.node) return;
    
    this.node.setAttribute('aria-live', priority);
    // Kosongkan sejenak agar perubahan textContent memicu event screen reader engine
    this.node.textContent = '';
    
    setTimeout(() => {
      this.node.textContent = message;
    }, 50);
  }
}
```

### Langkah 5: Modul Modal Lifecycle Orchestrator (`src/Modal.js`)
```javascript
import { FocusTrap } from './FocusTrap.js';

export class AccessibleModal {
  constructor(modalBackdropNode, triggerNode, announcer) {
    this.backdrop = modalBackdropNode;
    this.modal = this.backdrop.querySelector('[role="dialog"]');
    this.trigger = triggerNode;
    this.announcer = announcer;
    this.trap = new FocusTrap(this.modal);
    this.previouslyFocusedNode = null;

    this.initEvents();
  }

  initEvents() {
    this.backdrop.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.close('Dialog ditutup.');
      }
    });

    const closeButtons = this.modal.querySelectorAll('.btn-close, #cancel-btn');
    closeButtons.forEach(btn => {
      btn.addEventListener('click', () => this.close('Dialog dibatalkan.'));
    });
  }

  open() {
    this.previouslyFocusedNode = document.activeElement;
    this.backdrop.removeAttribute('hidden');
    
    // Cegah interaksi pada main content
    document.getElementById('main-content').setAttribute('inert', '');
    
    this.trap.activate();
    
    // Pindahkan fokus ke heading atau field pertama
    const firstInput = this.modal.querySelector('input');
    if (firstInput) {
      firstInput.focus();
    } else {
      this.modal.focus();
    }

    this.announcer.say('Dialog ubah kata sandi terbuka. Masukkan data yang diperlukan.');
  }

  close(announcementMessage) {
    this.trap.deactivate();
    this.backdrop.setAttribute('hidden', '');
    document.getElementById('main-content').removeAttribute('inert');

    if (this.previouslyFocusedNode && typeof this.previouslyFocusedNode.focus === 'function') {
      this.previouslyFocusedNode.focus();
    }

    if (announcementMessage) {
      this.announcer.say(announcementMessage);
    }
  }
}
```

### Langkah 6: Entry Point (`app.js`)
```javascript
import { Announcer } from './src/Announcer.js';
import { AccessibleModal } from './src/Modal.js';

const announcer = new Announcer('app-announcer');
const openBtn = document.getElementById('open-modal-btn');
const backdrop = document.getElementById('modal-backdrop');

const modal = new AccessibleModal(backdrop, openBtn, announcer);

openBtn.addEventListener('click', () => {
  modal.open();
});

const form = document.getElementById('password-form');
form.addEventListener('submit', (e) => {
  e.preventDefault();
  modal.close('Kata sandi berhasil diubah.');
});
```

---

## 13. Exercise

### Latihan 1 (Level: Easy)
Perbaiki elemen formulir berikut agar memenuhi kriteria **AccName Computation** tanpa mengubah bentuk fisik input di layar.
```html
<!-- KODE AWAL CACAT -->
<div class="search-box">
  <input type="text" placeholder="Cari pesanan...">
  <button><svg><path d="..."/></svg></button>
</div>
```
* **Acceptance Criteria**:
  1. Input memiliki label terkomputasi yang valid tanpa menampilkan visual label tambahan (gunakan CSS `.sr-only`).
  2. Tombol SVG ikon memiliki nama aksesibel "Submit Pencarian".
  3. Validasi AXTree di Chrome DevTools mengonfirmasi `role="textbox"` memiliki `name="Cari pesanan"` dan `role="button"` memiliki `name="Submit Pencarian"`.

### Latihan 2 (Level: Medium)
Rancang komponen **Accordion Panel Tunggal** (`aria-expanded`, `aria-controls`, `aria-labelledby`) murni dengan Vanilla JS:
* **Acceptance Criteria**:
  1. Header tombol bertindak sebagai trigger akordion.
  2. Ketika panel tertutup, kontainer konten panel memiliki atribut `hidden`.
  3. Penekanan tombol `Enter` atau `Space` pada header toggle membuka/menutup panel secara instan dan memperbarui nilai `aria-expanded` menjadi `true`/`false`.
  4. Atribut `aria-controls` pada tombol mengarah tepat ke `id` kontainer konten yang dikendalikan.

### Latihan 3 (Level: Hard)
Bangun arsitektur navigasi keyboard **Roving Tabindex Toolbar (1D Horizontal)** untuk rich text editor:
* **Acceptance Criteria**:
  1. Terdiri dari 4 kontrol tombol (`Bold`, `Italic`, `Underline`, `Link`).
  2. Elemen pertama memiliki `tabindex="0"`, 3 tombol lainnya memiliki `tabindex="-1"`.
  3. Saat fokus berada di dalam toolbar:
     - `ArrowRight` memindahkan fokus ke tombol berikutnya (melingkar dari terakhir ke pertama / cyclic rotation).
     - `ArrowLeft` memindahkan fokus ke tombol sebelumnya.
     - Tombol yang baru menerima fokus berubah menjadi `tabindex="0"`, sedangkan tombol lama diubah menjadi `tabindex="-1"`.
  4. Tab masuk hanya mendarat ke tombol aktif terakhir; Tab keluar membawa pengguna langsung ke elemen di luar container toolbar.

---

## 14. Challenge

### Studi Kasus: Accessible High-Volume Virtualized Data Grid (Stock Ticker)
Anda ditugaskan oleh institusi perbankan investasi multinasional untuk merancang sistem komponen headless data grid yang merender 50.000 instrumen derivatif dengan kriteria ketat:
1. **Viewport Limit**: Hanya 15 baris data yang dirender di DOM fisik dalam satu waktu.
2. **Keyboard Traversal 2D**: Pengguna tunanetra dan power-user motorik harus dapat bernavigasi menggunakan `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight` di antara cell tanpa kehilangan posisi koordinat logis ($x, y$), meskipun baris yang bersangkutan mengalami *mount/unmount* secara dinamis oleh algoritma virtual scrolling.
3. **Screen Reader Performance**: Baris data mengalami perubahan harga setiap 500 milidetik. Sistem dilarang membekukan speech engine screen reader. Rancang arsitektur buffer announcernya.
4. **Zero Mouse Dependency**: Operasi aksi baris (misal: "Beli", "Jual") harus dapat diakses melalui keyboard shortcut terdaftar tanpa membuyarkan titik koordinat fokus cell grid saat ini.

*Instruksi Eksekusi*: Susun rancangan arsitektur modul, spesifikasi pemetaan ARIA Role/Property, strategi manajemen state fokus (`aria-activedescendant` vs `Roving Tabindex`), dan algoritma proteksi live queue dalam dokumen teknis arsitektur lengkap berserta pseudocode core loop-nya.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic Knowledge
1. **Apa fungsi utama dari Accessibility Tree (AXTree) dalam browser?**
   * A. Mempercepat kalkulasi tata letak visual CSS (reflow).
   * B. Mengonversi struktur DOM & style menjadi format standar OS Accessibility API yang dapat dibaca Assistive Technology.
   * C. Menghubungkan browser engine langsung ke server pengujian aksesibilitas cloud.
   * D. Menghasilkan selector CSS secara otomatis.
   * *Jawaban*: **B**.

2. **Manakah dari atribut berikut yang memiliki preseden tertinggi dalam AccName Computation Algorithm?**
   * A. `aria-label`
   * B. `title`
   * C. Native `<label>` tag
   * D. `aria-labelledby`
   * *Jawaban*: **D**.

3. **Apa dampak langsung penerapan CSS `visibility: hidden` pada Accessibility Tree?**
   * A. Elemen tetap ada di AXTree namun diberi status disabled.
   * B. Elemen dan seluruh sub-pohonnya dihapus secara penuh dari AXTree.
   * C. Elemen hanya dibaca oleh screen reader jika memiliki atribut `aria-live`.
   * D. Elemen berubah secara otomatis menjadi `role="presentation"`.
   * *Jawaban*: **B**.

4. **Kapan atribut `aria-live="assertive"` harus digunakan?**
   * A. Pada setiap pembaruan data AJAX/Fetch di halaman web.
   * B. Hanya untuk pesan kritis berskala urgensi tinggi seperti session timeout atau system error.
   * C. Pada dropdown pagination menu.
   * D. Pada counter like postingan media sosial.
   * *Jawaban*: **B**.

5. **Apa fungsi dari atribut HTML5 `inert`?**
   * A. Memberikan animasi fading pada elemen latar belakang.
   * B. Memerintahkan mesin browser untuk mengabaikan seluruh interaksi keyboard/mouse dan menyembunyikan sub-tree dari AXTree secara native.
   * C. Mengaktifkan spellcheck bawaan browser pada form.
   * D. Menandai form submission yang bersifat non-blocking.
   * *Jawaban*: **B**.

---

### Bagian B: Intermediate Conceptual
6. **Mengapa menambahkan `role="button"` pada tag `<div>` tanpa atribut `tabindex` dianggap sebagai pelanggaran aksesibilitas serius?**
   * A. Tag `<div>` tidak bisa dirender oleh browser engine modern jika diberi role ARIA.
   * B. Menambahkan role hanya menyematkan semantik pada AXTree, namun tidak memberikan kemampuan fokus keyboard native maupun penanganan event Space/Enter.
   * C. Penggunaan role button otomatis menonaktifkan fitur CSS styling.
   * D. Hal tersebut menyebabkan syntax parsing error pada HTML parser.
   * *Jawaban*: **B**.

7. **Dalam pola Combobox 1.2, mengapa `aria-activedescendant` sering kali lebih disukai daripada `roving tabindex` untuk daftar opsi yang sangat panjang?**
   * A. Karena `roving tabindex` tidak didukung oleh browser Safari.
   * B. Karena `aria-activedescendant` mengeliminasi overhead mutasi atribut `tabindex` berulang pada setiap child node dan menjaga fokus DOM tetap di input field.
   * C. Karena `aria-activedescendant` otomatis menerjemahkan teks ke suara tanpa screen reader.
   * D. Karena `roving tabindex` memicu memory leak secara otomatis pada garbage collector JavaScript.
   * *Jawaban*: **B**.

8. **Perhatikan kode berikut: `<button aria-label="Simpan Dokumen">Unduh File</button>`. Teks apa yang diumumkan oleh screen reader?**
   * A. "Simpan Dokumen Unduh File"
   * B. "Unduh File"
   * C. "Simpan Dokumen"
   * D. Browser engine akan crash akibat konflik label.
   * *Jawaban*: **C**. (Sesuai AccName Spec, `aria-label` sepenuhnya menimpa/shadows text content anak elemen).

9. **Apa perbedaan teknis mendasar antara `aria-modal="true"` dengan penggunaan atribut native `inert` pada node di luar modal?**
   * A. `aria-modal="true"` memberikan instruksi ke screen reader bahwa elemen adalah modal, namun browser engine lama tidak memblokir navigasi Tab fisik ke background tanpa manipulasi focus trap manual atau atribut `inert`.
   * B. `inert` hanya bisa digunakan pada aplikasi mobile.
   * C. `aria-modal="true"` otomatis mematikan rendering grafis elemen di belakang modal.
   * D. Keduanya memiliki fungsi yang identik 100% di semua level mesin browser tanpa pengecualian.
   * *Jawaban*: **A**.

10. **Apa kegunaan dari atribut `aria-atomic="true"` pada elemen dengan `aria-live`?**
    * A. Menghapus pesan secara otomatis setelah 5 detik.
    * B. Memerintahkan screen reader untuk mempresentasikan seluruh isi kontainer secara komprehensif, bukan hanya node teks yang mengalami perubahan mikro.
    * C. Mengonversi teks di dalam kontainer menjadi format angka atomik.
    * D. Memaksa browser mengeksekusi script secara atomic synchronous.
    * *Jawaban*: **B**.

---

### Bagian C: Production Scenarios
11. **Skenario 1**: Tim Anda merilis fitur infinite-scroll feeding. Pengguna screen reader melaporkan bahwa ketika mereka menekan tombol Tab, browser tiba-tiba melompat ke footer situs tanpa dapat membaca postingan yang baru saja dimuat. Setelah diaudit, konten disuntikkan secara dinamis melalui REST API. Apa penyebab kegagalan arsitektur ini dan bagaimana solusinya?
    * *Solusi Teknis*:
      1. *Penyebab*: Elemen baru yang disuntikkan ke DOM tidak memiliki urutan DOM (*source order*) yang tepat sebelum footer, atau fokus secara tidak sengaja terlempar ke luar kontainer saat item baru sedang dalam fase loading un-mount/re-mount. Selain itu, tidak adanya live region announcement membuat pengguna AT tidak menyadari bahwa batch item baru telah ditambahkan.
      2. *Solusi*: Pastikan item baru disisipkan secara deterministik sebelum elemen trigger pagination. Letakkan pembaca status virtual via `aria-live="polite"` ("Memuat 10 konten baru... Konten 11 sampai 20 siap dilihat"). Pertahankan fokus keyboard pada item terakhir yang dibaca sebelum proses fetching dilakukan, bukan melepaskan fokus bebas ke body/footer.

12. **Skenario 2**: Anda mengaudit single-page application perbankan enterprise. Terdapat form transfer kustom dengan pesan validasi error inline: `<span class="error-text">Saldo tidak mencukupi</span>`. Namun, saat pengujian menggunakan NVDA, pembaca layar tidak mengumumkan error tersebut ketika tombol Submit ditekan, meskipun teks merah muncul di layar. Analisis di mana cacat implementasinya dan susun perbaikannya.
    * *Solusi Teknis*:
      1. *Penyebab*: Span error disuntikkan ke layar tanpa konfigurasi semantik input relation. Ketiadaan atribut `aria-invalid` pada field input rekening dan ketiadaan relasi `aria-errormessage` atau `aria-describedby` menyebabkan screen reader menganggap input dalam kondisi normal saat submit gagal.
      2. *Solusi*:
         - Pasang `aria-invalid="true"` pada elemen `<input id="input-saldo">`.
         - Pasang `aria-describedby="error-saldo-id"` pada input tersebut.
         - Berikan ID pada pesan error: `<span id="error-saldo-id" class="error-text">Saldo tidak mencukupi</span>`.
         - Pindahkan fokus programatik kembali ke `<input id="input-saldo">` sesaat setelah form submission ditolak agar screen reader langsung membaca label input, status invalid, dan pesan deskripsi error secara sekuensial.

13. **Skenario 3**: Sebuah modal konfirmasi penghapusan data dibangun menggunakan library pihak ketiga. Pengguna tunanetra mengeluhkan bahwa saat dialog muncul, jika mereka menekan tombol Tab terus menerus, fokus keyboard dapat mendarat pada navigasi navbar utama di latar belakang yang berada di balik overlay gelap. Mengapa hal ini terjadi dan bagaimana arsitektur Focus-Trap memperbaikinya secara menyeluruh?
    * *Solusi Teknis*:
      1. *Penyebab*: Modal hanya memanipulasi z-index visual dan opacity visual overlay tanpa mengunci *DOM Tab-sequence order*. Ini melanggar prinsip WAI-ARIA Modal Dialog Pattern. Elemen interaktif di luar modal tetap berada di dalam tab-order aktif browser.
      2. *Solusi Arsitektur*:
         - Mengaktifkan event listener `keydown` khusus pada boundary modal: Lacak elemen *first focusable* dan *last focusable*. Saat `Tab` ditekan pada last element, paksa `firstElement.focus()`. Saat `Shift + Tab` ditekan pada first element, paksa `lastElement.focus()`.
         - Terapkan atribut `inert` pada node sibling utama (`<main inert>`) saat modal terbuka untuk mematikan kemampuan aksesibilitas dan interaktivitas background sub-tree secara native oleh browser engine.

---

## 16. Summary

Aksesibilitas web mendalam (*Advanced Web Accessibility*) bukan sekadar menambahkan atribut visual atau atribut bantuan tambahan secara acak, melainkan rekayasa komprehensif terhadap **Accessibility Tree (AXTree)** browser. 

Kunci arsitektur aksesibilitas produksi meliputi:
1. **AccName Algorithm Consistency**: Menjamin seluruh elemen interaktif memiliki label yang valid dan deterministik tanpa polusi penimpaan (*label collision*).
2. **Keyboard Traversal Parity**: Setiap aksi mouse harus memiliki ekuivalen interaksi keyboard dua arah yang mematuhi standar authoring WAI-ARIA APG (meliputi Focus Trapping, Focus Restoration, dan Roving Selection).
3. **Controlled Live Communication**: Penggunaan live region terpusat untuk meminimalisasi tabrakan buffer audio, menjaga aplikasi tetap responsif dan informatif bagi pengguna Assistive Technology di bawah beban transfer data yang tinggi.