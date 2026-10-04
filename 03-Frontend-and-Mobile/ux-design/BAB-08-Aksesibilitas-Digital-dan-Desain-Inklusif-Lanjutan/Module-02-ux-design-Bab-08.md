# BAB 08: Aksesibilitas Digital dan Desain Inklusif Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis siklus hidup internal *Accessibility Tree* (AXTree) di dalam *browser rendering engine* dan bagaimana modifikasi DOM/CSSOM berdampak pada performa pohon aksesibilitas.
*   Merancang dan mengimplementasikan komponen UI dinamis berkategori kompleks (*custom widgets*) seperti *Combobox Autocomplete*, *Modal Dialog with Focus Trap*, dan *2D Virtualized Data Grid* sesuai spesifikasi WAI-ARIA 1.2 dan WCAG 2.2 Level AA/AAA.
*   Mengorkestrasi sistem manajemen fokus tingkat lanjut menggunakan *Roving Tabindex*, *Active Descendant*, dan API modern seperti `inert` HTML attribute.
*   Membangun arsitektur *Design System Tokens* inklusif yang mendukung kontras adaptif (*Light, Dark, High Contrast Mode*) serta integrasi otomatis pengujian aksesibilitas (*axe-core*, Playwright CI/CD pipeline).
*   Mengatasi permasalahan skalabilitas pada antarmuka *real-time* berbasis WebSocket tanpa membanjiri *Screen Reader* melalui pola *ARIA Live Region Throttling & Queuing*.

---

### 2. Prerequisite
Untuk mencerna materi ini secara komprehensif, Anda harus menguasai:
*   **Arsitektur Frontend Modern:** DOM API, Virtual DOM/Reconciliation, CSS Box Model, Custom Events, dan State Management berbasis Hooks/Signals.
*   **TypeScript & React/Web Components:** Pengetikan statis tingkat lanjut (*generics*, *discriminated unions*), *lifecycle effects*, dan manipulasi ref tingkat rendah.
*   **Fondasi Aksesibilitas Web:** Pemahaman dasar tentang HTML Semantik, WCAG 2.1 Four Principles (POUR: *Perceivable, Operable, Understandable, Robust*), serta pengalaman dasar mengoperasikan salah satu *Assistive Technology* (Apple VoiceOver, NVDA, atau Orca).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Siklus Hidup Accessibility Tree (AXTree) dan OS Accessibility API
Browser modern (Chromium/Blink, Gecko, WebKit) tidak memaparkan DOM mentah langsung ke perangkat pembaca layar (*screen reader*). Sebaliknya, *rendering engine* membangun struktur data paralel yang disebut **Accessibility Tree (AXTree)**.

```
+-------------+      +-------------+
|   DOM Tree  |  +   |  CSSOM Tree |
+------+------+      +------+------+
       |                    |
       v                    v
+----------------------------------+
|          Layout / Render Tree    |
+------------------+---------------+
                   |
                   v
+----------------------------------+
|    Accessibility Tree (AXTree)   |
|   (Roles, States, Names, Values) |
+------------------+---------------+
                   |
    Platform Accessibility API Bridge
   (UIA, NSAccessibility, AT-SPI)
                   |
                   v
+----------------------------------+
|       Assistive Technology       |
|    (NVDA, VoiceOver, JAWS)       |
+----------------------------------+
```

1. **DOM Tree + CSSOM Tree Generation:** Browser melakukan parsing HTML dan CSS.
2. **Render/Layout Tree:** Objek yang memiliki `display: none` atau atribut `hidden` akan dikeluarkan dari layout pipeline. Objek dengan `visibility: hidden` tetap berada di layout tree tetapi tidak digambar secara visual.
3. **AXTree Generation:** Browser mengonstruksi simpul-simpul aksesibilitas (*AXNode*). Setiap *AXNode* menyimpan:
   * **Role:** Peran elemen (misal: `button`, `combobox`, `dialog`, `gridcell`).
   * **Name (Accessible Name):** Dihitung melalui algoritma *Accessible Name and Description Computation* (AccName Mappings: urutan prioritas `aria-labelledby` > `aria-label` > native semantics seperti `<label>` atau `alt` > teks internal).
   * **Description:** Nilai sekunder dari `aria-describedby` atau *title*.
   * **State/Properties:** `aria-expanded`, `aria-checked`, `aria-disabled`, `aria-activedescendant`, dll.
4. **Platform Bridge:** AXTree dipetakan ke API native sistem operasi:
   * Windows: UI Automation (UIA) & IAccessible2 (IA2).
   * macOS / iOS: NSAccessibility / UIAccessibility.
   * Linux: AT-SPI2.
   * Android: AccessibilityNodeInfo.

#### Masalah Dual-Tree Synchronization & Layout Thrashing
Setiap mutasi DOM dinamis melalui JavaScript memicu mutasi pada AXTree. Jika pengembang melakukan mutasi ARIA state yang tidak terkoordinasi (misal, mengubah `aria-expanded` ratusan kali dalam satu detik pada animasi atau *stream data*), browser terpaksa merekonstruksi sebagian dari AXTree (*invalidation*). Hal ini menyebabkan *frame drops* (penurunan frame rate) dan *assistive tech latency*—kondisi di mana pembaca layar tertinggal hingga beberapa detik di belakang UI visual.

---

### 4. Why & What

#### Why: Mengapa Pendekatan Simpel Selalu Gagal di Skala Enterprise?
Pengujian otomatis menggunakan alat seperti Lighthouse atau *static linter* hanya mampu menangkap 30% hingga 40% dari total potensi pelanggaran aksesibilitas. Kode dapat memiliki skor 100% pada Lighthouse tetapi tetap **100% tidak dapat digunakan** oleh tunanetra karena:
* *Keyboard Trap:* Fokus terjebak di dalam elemen tanpa jalan keluar.
* *Lost Context:* Modal ditutup, fokus terlempar ke elemen `<body>`, memaksa pengguna membaca ulang antarmuka dari awal.
* *Silent Dynamic Updates:* Konten berubah via WebSocket, namun antarmuka tidak memancarkan sinyal ke AXTree melalui *polite live regions*.
* *Incoherent Keyboard Matrix:* Konten berbentuk tabel data interaktif hanya bisa ditelusuri dengan tombol `Tab` ratusan kali, melanggar pola *Composite Widget Keyboard Navigation*.

#### What: Solusi Arsitektural
Modul ini mendasarkan implementasi pada arsitektur produksi:
1. **Focus Orchestration Engine:** Pola terpusat untuk menjamin *Focus Containment*, *Focus Restoration*, dan *Virtual Focus Management*.
2. **Accessible Object Model (AOM) Mindset:** Memanipulasi state aksesibilitas layaknya struktur data rekayasa perangkat lunak formal, bukan sekadar penambahan string atribut arbitrer di template HTML.
3. **Adaptive Contrast Tokens:** Penanganan tema kontras tinggi (*Windows Contrast Mode/Forced Colors*) menggunakan CSS modern (*System Colors* dan `@media (forced-colors: active)`).

---

### 5. How (Workflow Detail)

Alur kerja rekayasa komponen interaktif inklusif:

```
[Requirement Spec (WCAG 2.2 AA)]
               |
               v
[1. Definisi State Machine Komponen]
  - State: Closed, Open, Searching, Navigating
  - Transition: KeyDown, Blur, Select
               |
               v
[2. Pemetaan Accessible Roles & Relationships]
  - Parent: role="combobox"
  - Child Popover: role="listbox"
  - Items: role="option"
  - Relations: aria-controls, aria-owns, aria-activedescendant
               |
               v
[3. Implementasi Focus & Keyboard Strategy]
  - Native Focus vs Virtual Focus (aria-activedescendant)
  - Key bindings: Escape, Enter, ArrowUp, ArrowDown, Tab
               |
               v
[4. Telemetri & Synchronous Fallbacks]
  - Fallback untuk API modern (HTMLDialogElement vs inert polyfill)
  - Throttled Live Regions untuk screen reader output
               |
               v
[5. Automated CI/CD Regression Gate]
  - Playwright + @axe-core/playwright
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Bandara Internasional
*   **DOM Tree:** Denah fisik bangunan bandara (dinding, pintu, eskalator, terminal).
*   **CSSOM/Render Tree:** Desain interior, lampu penerangan, dan dekorasi estetik.
*   **Accessibility Tree:** Papan petunjuk rute taktil dan pengumuman audio melalui interkom (*Public Address System*).
*   **Focus Management:** Petugas darat (*Ground Staff*) yang memandu penumpang ke gerbang yang tepat tanpa membiarkan penumpang tersesat di koridor terisolasi (*Focus Trap* yang terkontrol).
*   **Screen Reader:** Penumpang yang sepenuhnya bergantung pada interkom dan peta taktil untuk menavigasi seluruh bandara.

#### Diagram Roving Tabindex vs Active Descendant

```
STRATEGI 1: Roving Tabindex
(DOM Focus berpindah secara fisik)
+---------------+      +---------------+      +---------------+
| Item 1        |      | Item 2        |      | Item 3        |
| tabindex="0"  | ---> | tabindex="-1" | ---> | tabindex="-1" |
| (FOKUS AKTIF) | [->] | (FOKUS DI SINI|      |               |
+---------------+      +---------------+      +---------------+

STRATEGI 2: Virtual Focus via aria-activedescendant
(DOM Focus tetap berada pada Input/Container, DOM node target dipetakan via ID)
+-------------------------------------------------------------+
| Input Box: role="combobox"                                   |
| tabindex="0" (DOM FOCUS PERMANEN)                           |
| aria-activedescendant="opt-2"                               |
+-------------------------------------------------------------+
     |
     +--------------------------------+
                                      v
+---------------+      +-------------------------------+      +---------------+
| Item 1        |      | Item 2 (id="opt-2")           |      | Item 3        |
| role="option" |      | role="option"                 |      | role="option" |
|               |      | [TERPILIH SECARA VIRTUAL AX]  |      |               |
+---------------+      +-------------------------------+      +---------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Accessible Disclosure (Native HTML vs ARIA)
Pendekatan semantik native selalu mengungguli implementasi manual ARIA:

```html
<!-- Native: Browser menangani AXTree, peranan, dan penekanan Spasi/Enter secara otomatis -->
<details>
  <summary>Spesifikasi Teknis Mesin</summary>
  <p>Detail performa motor induksi 3-fasa 50Hz 400V.</p>
</details>
```

Jika terpaksa menggunakan custom element:

```tsx
import React, { useState, useId } from 'react';

export const CustomDisclosure: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const contentId = useId();

  return (
    <div>
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setIsOpen((prev) => !prev)}
        className="disclosure-btn"
      >
        {title}
      </button>
      <div
        id={contentId}
        role="region"
        hidden={!isOpen}
        className="disclosure-panel"
      >
        {children}
      </div>
    </div>
  );
};
```

#### 7.2 Practical Example (Enterprise Standard): High-Performance Accessible Combobox (Autocomplete)
Implementasi pola WAI-ARIA 1.2 Combobox dengan virtual focus (`aria-activedescendant`), keyboard matrix lengkap, dan penanganan kontras tinggi.

```tsx
import React, {
  useState,
  useRef,
  useId,
  useCallback,
  KeyboardEvent,
  ChangeEvent,
} from 'react';

export interface ComboboxOption {
  id: string;
  label: string;
  value: string;
}

interface AccessibleComboboxProps {
  label: string;
  options: ComboboxOption[];
  onSelect: (option: ComboboxOption) => void;
  placeholder?: string;
}

export const AccessibleCombobox: React.FC<AccessibleComboboxProps> = ({
  label,
  options,
  onSelect,
  placeholder,
}) => {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number>(-1);

  const baseId = useId();
  const inputId = `${baseId}-input`;
  const listboxId = `${baseId}-listbox`;
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredOptions = options.filter((opt) =>
    opt.label.toLowerCase().includes(query.toLowerCase())
  );

  const activeOptionId =
    activeIndex >= 0 && activeIndex < filteredOptions.length
      ? `${baseId}-opt-${filteredOptions[activeIndex].id}`
      : undefined;

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    setIsOpen(true);
    setActiveIndex(0);
  };

  const handleSelect = useCallback(
    (index: number) => {
      const selected = filteredOptions[index];
      if (selected) {
        setQuery(selected.label);
        onSelect(selected);
        setIsOpen(false);
        setActiveIndex(-1);
        inputRef.current?.focus();
      }
    },
    [filteredOptions, onSelect]
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setActiveIndex(0);
        } else {
          setActiveIndex((prev) =>
            prev < filteredOptions.length - 1 ? prev + 1 : 0
          );
        }
        break;

      case 'ArrowUp':
        e.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setActiveIndex(filteredOptions.length - 1);
        } else {
          setActiveIndex((prev) =>
            prev > 0 ? prev - 1 : filteredOptions.length - 1
          );
        }
        break;

      case 'Enter':
        if (isOpen && activeIndex >= 0) {
          e.preventDefault();
          handleSelect(activeIndex);
        }
        break;

      case 'Escape':
        if (isOpen) {
          e.preventDefault();
          setIsOpen(false);
          setActiveIndex(-1);
        }
        break;

      case 'Tab':
        if (isOpen) {
          setIsOpen(false);
          setActiveIndex(-1);
        }
        break;

      default:
        break;
    }
  };

  return (
    <div className="combobox-wrapper">
      <label id={`${baseId}-label`} htmlFor={inputId} className="combobox-label">
        {label}
      </label>

      <div className="combobox-input-container">
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-controls={listboxId}
          aria-activedescendant={activeOptionId}
          aria-labelledby={`${baseId}-label`}
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => query && setIsOpen(true)}
          placeholder={placeholder}
          className="combobox-input"
        />
      </div>

      {isOpen && (
        <ul
          id={listboxId}
          role="listbox"
          aria-labelledby={`${baseId}-label`}
          className="combobox-listbox"
        >
          {filteredOptions.length === 0 ? (
            <li role="presentation" className="combobox-option-empty">
              Data tidak ditemukan
            </li>
          ) : (
            filteredOptions.map((opt, index) => {
              const isSelected = index === activeIndex;
              return (
                <li
                  key={opt.id}
                  id={`${baseId}-opt-${opt.id}`}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => handleSelect(index)}
                  className={`combobox-option ${isSelected ? 'is-active' : ''}`}
                >
                  {opt.label}
                </li>
              );
            })
          )}
        </ul>
      )}

      {/* ARIA Live Region for asynchronous screen-reader feedback */}
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {isOpen &&
          `${filteredOptions.length} hasil tersedia. Gunakan panah atas dan bawah untuk navigasi.`}
      </div>
    </div>
  );
};
```

```css
/* Dukungan High Contrast Mode (WHCM) dan Aksesibilitas Visual */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.combobox-wrapper {
  position: relative;
  font-family: system-ui, -apple-system, sans-serif;
  width: 100%;
  max-width: 380px;
}

.combobox-input {
  width: 100%;
  padding: 10px 14px;
  font-size: 1rem;
  border: 2px solid #4a5568;
  border-radius: 6px;
  outline-offset: 2px;
}

.combobox-input:focus {
  outline: 3px solid #2b6cb0;
}

.combobox-listbox {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin: 4px 0 0 0;
  padding: 0;
  list-style: none;
  background: #ffffff;
  border: 2px solid #4a5568;
  border-radius: 6px;
  max-height: 240px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.combobox-option {
  padding: 10px 14px;
  cursor: pointer;
}

.combobox-option.is-active {
  background-color: #ebf8ff;
  color: #2b6cb0;
  font-weight: 600;
}

/* Penanganan Khusus Windows High Contrast Mode / Forced Colors */
@media (forced-colors: active) {
  .combobox-input:focus {
    outline: 3px solid Highlight;
  }
  .combobox-option.is-active {
    background-color: Highlight;
    color: HighlightText;
    forced-color-adjust: none;
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Real-Time FX Trading Terminal (PT Bank Sentral Finansial)
*   **Konteks Masalah:** Aplikasi web perdagangan valas (FX) internal bank menampilkan buku pesanan (*Order Book*) dan pergerakan kurs mata uang secara live via WebSocket dengan frekuensi rata-rata 40 update/detik.
*   **Permasalahan Aksesibilitas:** 
    1. Tim UX sebelumnya menyematkan `aria-live="assertive"` langsung ke seluruh kontainer tabel kurs.
    2. *Dampak:* Screen reader milik staf dealer tunanetra mengalami *audio freeze*, buffer suara menumpuk hingga 4 menit di belakang pasar real-time, browser mengalami *memory leak* akibat AXTree mutations overload.
*   **Solusi Rekayasa:**
    1. **Pemisahan Visual Pipeline vs Auditory Pipeline:** Membatalkan seluruh `aria-live` langsung pada node tabel. Mengubah tabel menjadi pola `role="grid"` interaktif 2 dimensi dengan *Roving Tabindex*. Staf dapat menelusuri sel spesifik (misal Kurs Beli EUR/USD) menggunakan tombol arah keyboard tanpa pembacaan otomatis yang tak diminta.
    2. **Throttled Delta Live Region:** Membangun *Audio Dispatcher Engine* yang mengagregasi lonjakan pergerakan harga (*price spike* > 0.5%) melalui mekanisme *debounced live region*.

```typescript
// Production Throttled A11y Alert Dispatcher
class AccessibleAlertBroker {
  private queue: string[] = [];
  private isProcessing = false;
  private alertContainer: HTMLElement;

  constructor() {
    const el = document.createElement('div');
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.className = 'sr-only';
    document.body.appendChild(el);
    this.alertContainer = el;
  }

  public dispatch(message: string, priority: 'immediate' | 'batch' = 'batch') {
    if (priority === 'immediate') {
      this.alertContainer.textContent = message;
      return;
    }

    this.queue.push(message);
    if (!this.isProcessing) {
      this.processQueue();
    }
  }

  private processQueue() {
    if (this.queue.length === 0) {
      this.isProcessing = false;
      return;
    }

    this.isProcessing = true;
    const latestNotice = this.queue.pop(); // Ambil delta terbaru, buang stale updates
    this.queue = []; // Flush buffer

    if (latestNotice) {
      this.alertContainer.textContent = latestNotice;
    }

    setTimeout(() => {
      this.processQueue();
    }, 3000); // Window 3 detik memberikan jeda audio yang ergonomis bagi Assistive Tech
  }
}

export const fxA11yBroker = new AccessibleAlertBroker();
```

*   **Hasil:** Penurunan degradasi memori browser hingga 82%, penghapusan total *audio lag*, dan kelulusan audit audit regulasi kepatuhan WCAG 2.2 Level AA untuk terminal perdagangan bank tersebut.

---

### 9. Trade-offs (Analisis Kompromi Teknis)

| Pendekatan Rekayasa | Keuntungan | Kerugian / Biaya | Konsekuensi Produksi |
| :--- | :--- | :--- | :--- |
| **Native HTML Semantics** (`<dialog>`, `<select>`, `<button>`) | Kompatibilitas OS 100%, zero runtime overhead, navigasi keyboard ditangani native oleh browser engine. | Sangat sulit di-styling secara konsisten di semua browser; kemampuan animasi terbatas. | Opsi mutlak untuk aplikasi publik dengan variasi perangkat ekstrim. |
| **Custom ARIA Widgets (Aria Pattern Replication)** | Kontrol styling 100%, fleksibel untuk interaksi visual kompleks. | Biaya perawatan tinggi; rawan bug fokus; harus menulis seluruh keyboard state machine secara manual. | Wajib didampingi *End-to-End accessibility test coverage* yang ketat di CI/CD. |
| **Virtual Focus (`aria-activedescendant`)** | Tidak memicu relayout fisik DOM saat seleksi; scroll container tetap stabil. | Masalah kompatibilitas pada pembaca layar generasi lama di perangkat mobile (Android TalkBack). | Sangat unggul untuk daftar besar (*virtualized list* ribuan node). |
| **Physical Focus (`Roving Tabindex`)** | Kompatibilitas universal di seluruh screen reader desktop dan mobile. | Mutasi atribut `tabindex` secara masif di banyak DOM nodes; kompleksitas kalkulasi unmount/mount. | Sangat ideal untuk Toolbar, Menu bar, dan Grid tabulasi. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah: Focus Trap Membocorkan Interaksi ke Latar Belakang
*   **Kesalahan:** Mengembangkan modal dialog khusus (`<div role="dialog">`), tetapi elemen di belakangnya tetap dapat dijangkau pengguna dengan menekan tombol `Tab`.
*   **Deteksi:** Uji dengan keyboard saja: Buka modal dialog, tekan `Tab` berulang kali. Jika selektor fokus biru berpindah ke link di navbar luar modal, fokus bocor.
*   **Solusi:** Gunakan atribut standar modern `inert` pada node pembungkus aplikasi utama saat modal terbuka, atau tangkap fokus secara deterministik:

```typescript
// Utility mengunci fokus di dalam container modal
export function trapFocus(container: HTMLElement, event: KeyboardEvent) {
  if (event.key !== 'Tab') return;

  const focusables = container.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const firstFocusable = focusables[0];
  const lastFocusable = focusables[focusables.length - 1];

  if (event.shiftKey) {
    if (document.activeElement === firstFocusable) {
      lastFocusable.focus();
      event.preventDefault();
    }
  } else {
    if (document.activeElement === lastFocusable) {
      firstFocusable.focus();
      event.preventDefault();
    }
  }
}
```

#### 2. Masalah: Visual Focus Hilang Tanpa Jejak
*   **Kesalahan:** Menghilangkan styling outline bawaan menggunakan:
    ```css
    * { outline: none; } /* ANTI-PATTERN BERBAHAYA */
    ```
*   **Solusi:** Selalu gunakan pseudo-class modern `:focus-visible` agar pengguna mouse tidak melihat outline yang mengganggu, tetapi navigasi keyboard tetap memiliki indikator kontras tinggi:
    ```css
    :focus:not(:focus-visible) {
      outline: none;
    }
    :focus-visible {
      outline: 3px solid #005fcc;
      outline-offset: 3px;
    }
    ```

---

### 11. Best Practices (Production Checklist)

#### Tim Design System & Frontend Architecture
*   [ ] **AccName Calculation Check:** Seluruh elemen interaktif memiliki Accessible Name yang unik dan deskriptif tanpa mengandalkan teks placeholder input.
*   [ ] **Inert Attribute Adoption:** Menggunakan atribut HTML `inert` pada kontainer root ketika sub-tree modal/drawer dirender.
*   [ ] **Contrast Ratios Verified:** Teks reguler memiliki rasio kontras minimal 4.5:1 terhadap latar belakang; teks besar (bold 14pt atau regular 18pt) memiliki minimal 3:1. Elemen non-teks antarmuka (garis border input, ikon interaktif) minimal 3:1 (WCAG 2.2 Non-text Contrast).
*   [ ] **Target Size Criterion:** Target klik/sentuh interaktif memiliki area fisik minimal 24x24 CSS pixels (WCAG 2.2 SC 2.5.8 Target Size Minimum).
*   [ ] **Escape Key Contract:** Seluruh elemen overlay (Modal, Popover, Menu, Tooltip) harus dapat ditutup secara instan menggunakan satu penekanan tombol `Escape`.
*   [ ] **Focus Restoration:** Ketika popover/dialog ditutup, fokus DOM wajib dikembalikan secara terprogram ke elemen pemicu (*trigger button*).
*   [ ] **No Assertive Live Spam:** Batasi penggunaan `aria-live="assertive"` hanya untuk kondisi darurat (*fatal error*, kehilangan koneksi jaringan, batas waktu transaksi).
*   [ ] **Reduced Motion Compliant:** Seluruh animasi antarmuka dimatikan atau direduksi jika terdeteksi preferensi sistem:
    ```css
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
      }
    }
    ```
*   [ ] **Automated CI Regression:** axe-core diintegrasikan ke dalam unit tests (Jest/Vitest) dan end-to-end tests (Playwright).

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori repositori: `hands-on/m02/`

```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── AccessibleDataGrid.tsx
│   ├── data.ts
│   └── index.tsx
└── tests/
    └── datagrid.a11y.spec.ts
```

#### Langkah 1: Inisialisasi Project dependencies
Buat file `hands-on/m02/package.json`:

```json
{
  "name": "a11y-m02-hands-on",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "test:a11y": "playwright test"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@axe-core/playwright": "^4.8.0",
    "@playwright/test": "^1.40.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.0.0"
  }
}
```

#### Langkah 2: Mengembangkan Accessible Data Grid 2D (Roving Tabindex Matrix)
Buat file `hands-on/m02/src/AccessibleDataGrid.tsx`:

```tsx
import React, { useState, useRef, KeyboardEvent } from 'react';

export interface GridColumn {
  key: string;
  header: string;
}

export interface GridRow {
  id: string;
  [key: string]: any;
}

interface AccessibleDataGridProps {
  caption: string;
  columns: GridColumn[];
  rows: GridRow[];
}

export const AccessibleDataGrid: React.FC<AccessibleDataGridProps> = ({
  caption,
  columns,
  rows,
}) => {
  // Posisi fokus 2D: [rowIndex, colIndex]. -1 menunjukkan baris header
  const [focusedCell, setFocusedCell] = useState<{ row: number; col: number }>({
    row: 0,
    col: 0,
  });

  const gridRef = useRef<HTMLTableElement>(null);

  const handleKeyDown = (e: KeyboardEvent<HTMLTableElement>) => {
    const totalRows = rows.length;
    const totalCols = columns.length;

    let { row, col } = focusedCell;

    switch (e.key) {
      case 'ArrowRight':
        e.preventDefault();
        if (col < totalCols - 1) col++;
        break;
      case 'ArrowLeft':
        e.preventDefault();
        if (col > 0) col--;
        break;
      case 'ArrowDown':
        e.preventDefault();
        if (row < totalRows - 1) row++;
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (row > 0) row--;
        break;
      case 'Home':
        e.preventDefault();
        col = 0;
        break;
      case 'End':
        e.preventDefault();
        col = totalCols - 1;
        break;
      default:
        return;
    }

    setFocusedCell({ row, col });

    // Pindahkan fokus fisik DOM ke sel yang bersesuaian
    const cellElement = gridRef.current?.querySelector<HTMLElement>(
      `[data-row="${row}"][data-col="${col}"]`
    );
    cellElement?.focus();
  };

  return (
    <div className="grid-container">
      <table
        ref={gridRef}
        role="grid"
        aria-label={caption}
        onKeyDown={handleKeyDown}
        className="accessible-grid"
      >
        <thead>
          <tr role="row">
            {columns.map((col, cIndex) => (
              <th
                key={col.key}
                role="columnheader"
                scope="col"
                className="grid-header"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, rIndex) => (
            <tr key={r.id} role="row">
              {columns.map((c, cIndex) => {
                const isSelected =
                  focusedCell.row === rIndex && focusedCell.col === cIndex;
                return (
                  <td
                    key={c.key}
                    role="gridcell"
                    data-row={rIndex}
                    data-col={cIndex}
                    tabIndex={isSelected ? 0 : -1}
                    className={`grid-cell ${isSelected ? 'cell-focused' : ''}`}
                    onClick={() => setFocusedCell({ row: rIndex, col: cIndex })}
                  >
                    {r[c.key]}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

#### Langkah 3: Integrasi Pengujian Otomatis Axe-Core + Playwright
Buat file `hands-on/m02/tests/datagrid.a11y.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility Quality Gate: DataGrid Widget', () => {
  test('Harus lulus audit WCAG 2.2 AA tanpa pelanggaran kritis', async ({ page }) => {
    // Navigasi ke instance pengujian komponen lokal
    await page.goto('http://localhost:3000');

    // Pastikan widget grid dirender sempurna
    await page.waitForSelector('table[role="grid"]');

    // Eksekusi pemindaian mesin axe-core
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();

    // Verifikasi zero violation
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Harus memindahkan koordinat fokus secara benar menggunakan panah keyboard', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    const firstCell = page.locator('[data-row="0"][data-col="0"]');
    await firstCell.focus();
    await expect(firstCell).toBeFocused();

    // Tekan Panah Kanan -> Fokus ke [0, 1]
    await page.keyboard.press('ArrowRight');
    const secondCell = page.locator('[data-row="0"][data-col="1"]');
    await expect(secondCell).toBeFocused();

    // Tekan Panah Bawah -> Fokus ke [1, 1]
    await page.keyboard.press('ArrowDown');
    const cellBelow = page.locator('[data-row="1"][data-col="1"]');
    await expect(cellBelow).toBeFocused();
  });
});
```

---

### 13. Exercise

#### Level Easy
Buat komponen tombol *Icon Button* (hanya menampilkan ikon SVG tanpa teks visual) yang memenuhi kriteria *Accessible Name*. Tombol harus menyediakan tooltip yang terbaca oleh screen reader dan muncul saat status `:focus-visible` aktif.

#### Level Medium
Kembangkan komponen *Accessible Tabs* (`role="tablist"`, `role="tab"`, `role="tabpanel"`). Terapkan navigasi keyboard:
* Panah Kanan/Kiri berpindah antar tab.
* Penekanan tombol `Home` langsung ke tab pertama; `End` ke tab terakhir.
* Atribut `aria-selected`, `aria-controls`, dan sinkronisasi fokus berjalan instan.

#### Level Hard
Rancang komponen *Virtual Infinite List* yang menampilkan 10.000 riwayat transaksi bank. Komponen harus:
* Hanya me-mount 20 node DOM aktif sesuai posisi scroll window (*Windowing Technique*).
* Tetap mengumumkan total ukuran koleksi ke screen reader (`aria-setsize="10000"` dan `aria-posinset="n"`).
* Mendukung navigasi panah atas/bawah tanpa merusak posisi scroll layar.

---

### 14. Challenge

**Skenario Tantangan Produksi:**
Anda ditugaskan mendesain ulang antarmuka formulir transfer dana antarbank dengan fitur verifikasi Biometrik WebAuthn dan PIN dinamis di mana keypad angka diacak posisinya (*scrambled numeric keypad*) demi keamanan mitigasi *shoulder-surfing*.

**Batasan Masalah:**
1. Keypad yang diacak secara visual membingungkan pengguna dengan gangguan motorik dan pengguna screen reader jika pengacakan mengubah urutan pembacaan audio.
2. Form tunduk pada regulasi perbankan ketat (kepatuhan WCAG 2.2 AAA pada area form autentikasi).
3. Anda dilarang mematikan fitur pengacakan keypad untuk pengguna nondisabilitas.

**Tugas Anda:**
Rancang arsitektur interaksi UX teknis, spesifikasi komponen, dan pemetaan *Accessibility Tree* yang menjamin keamanan perbankan tetap 100% aktif tanpa menciptakan diskriminasi aksesibilitas bagi pengguna difabel. Sertakan alur mitigasi keyboard dan strategi pengumuman status!

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Apa perbedaan mendasar antara DOM Tree dan Accessibility Tree (AXTree)?
   * A. DOM Tree menyimpan data styling, AXTree hanya menyimpan teks murni.
   * B. AXTree merupakan struktur data turunan yang mengekstrak peran semantik, state, dan accessible name untuk dipaparkan ke Accessibility API OS.
   * C. AXTree hanya aktif jika aplikasi web dibuka pada sistem operasi Windows.
   * D. DOM Tree dibuat oleh JavaScript engine, sedangkan AXTree dibuat oleh CSS engine.
   * *Jawaban:* **B**. Browser mengompilasi DOM dan CSSOM ke dalam AXTree untuk dipetakan ke API native sistem operasi pembaca layar.

2. Atribut apa yang digunakan untuk menyembunyikan elemen secara total dari pengguna visual maupun Screen Reader secara semantik native?
   * A. `aria-hidden="true"`
   * B. `opacity: 0`
   * C. Atribut HTML `hidden` atau CSS `display: none`
   * D. `tabindex="-1"`
   * *Jawaban:* **C**. `hidden` atau `display: none` mencabut elemen dari Layout Tree dan AXTree secara bersamaan.

3. Berapakah rasio kontras warna minimum yang diwajibkan oleh WCAG 2.2 Level AA untuk teks berukuran normal (di bawah 18pt reguler / 14pt bold)?
   * A. 3:1
   * B. 4.5:1
   * C. 7:1
   * D. 10:1
   * *Jawaban:* **B**. Standar WCAG 2.2 SC 1.4.3 mensyaratkan minimal 4.5:1 untuk teks berukuran normal.

4. Manakah elemen HTML yang secara otomatis menangani mekanisme *focus trap* dan *top-layer stacking* secara native tanpa library tambahan?
   * A. `<section role="dialog">`
   * B. `<aside>`
   * C. `<dialog>` yang dibuka menggunakan method `.showModal()`
   * D. `<form method="dialog">`
   * *Jawaban:* **C**. Pemanggilan `HTMLDialogElement.showModal()` membuka dialog di native top-layer browser lengkap dengan focus trap dan pembatalan interaksi latar belakang.

5. Apa efek dari pemberian atribut `aria-hidden="true"` pada elemen input formulir?
   * A. Input menjadi disabled dan tidak bisa diketik.
   * B. Input disembunyikan dari layar monitor.
   * C. Input disembunyikan dari Assistive Technology, namun pengguna keyboard masih dapat memfokuskan kursor ke dalamnya (menciptakan antarmuka hantu).
   * D. Input otomatis berubah menjadi password masked.
   * *Jawaban:* **C**. `aria-hidden="true"` tidak memutus kemampuan fokus keyboard native, sehingga menciptakan pengalaman yang membingungkan bagi pengguna keyboard nondisplay.

---

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)

6. Kapan sebaiknya Anda menggunakan `aria-live="assertive"` dibandingkan `aria-live="polite"`?
   * A. Setiap kali data di tabel bertambah.
   * B. Ketika menampilkan error validasi form biasa.
   * C. Hanya ketika ada notifikasi kritis yang membutuhkan interupsi langsung terhadap ucapan screen reader saat itu juga (misal: Sesi timeout dalam 30 detik).
   * D. Pada saat animasi loading sedang berputar.
   * *Jawaban:* **C**. `assertive` langsung memotong antrean audio assistif; jika disalahgunakan untuk event nonkritis, ini akan merusak pemahaman pengguna.

7. Perhatikan potongan kode berikut:
   ```html
   <button onclick="doAction()" aria-label="Tutup" title="Keluar">
     <span>X</span>
   </button>
   ```
   Berdasarkan spesifikasi *Accessible Name and Description Computation*, nama apa yang akan diumumkan oleh Screen Reader untuk tombol tersebut?
   * A. "X"
   * B. "Keluar"
   * C. "Tutup"
   * D. "Tutup Keluar X"
   * *Jawaban:* **C**. `aria-label` memiliki preseden prioritas lebih tinggi daripada `title` maupun teks isi elemen anak.

8. Apa fungsi dari atribut HTML modern `inert`?
   * A. Menambahkan efek animasi fade-in pada node DOM.
   * B. Membuat seluruh sub-tree elemen menjadi tidak dapat difokuskan, tidak dapat diklik, dan sepenuhnya diabaikan oleh Accessibility Tree.
   * C. Mengompresi ukuran payload data transfer elemen.
   * D. Menandai bahwa elemen tersebut berisi skrip JavaScript yang tidak aktif.
   * *Jawaban:* **B**. Atribut boolean `inert` memerintahkan browser untuk memperlakukan sub-tree tersebut seolah-olah tidak ada untuk interaksi penunjuk, keyboard, maupun pembaca layar.

9. Manakah pernyataan yang BENAR mengenai teknik navigasi keyboard *Roving Tabindex*?
   * A. Seluruh elemen anak dalam widget diberi nilai atribut `tabindex="0"`.
   * B. Hanya elemen aktif yang memiliki atribut `tabindex="0"`, sedangkan elemen pasif lainnya memiliki `tabindex="-1"`.
   * C. Fokus fisik DOM tidak pernah berpindah dari elemen input induk.
   * D. Widget sama sekali tidak dapat dioperasikan menggunakan tombol Tab.
   * *Jawaban:* **B**. Roving Tabindex menggeser nilai `0` dan `-1` secara dinamis mengikuti arah panah pengguna.

10. Apa tujuan dari kriteria sukses WCAG 2.2 terbaru: SC 2.5.8 (Target Size - Minimum)?
    * A. Menjamin resolusi gambar minimal 300 DPI.
    * B. Memastikan target pointer memiliki ukuran fisik minimal 24x24 CSS piksel atau memiliki jarak spasi yang memadai terhadap elemen interaktif terdekat.
    * C. Memastikan ukuran font minimal 16px pada perangkat mobile.
    * D. Mengatur ukuran maksimal layar viewport monitor pengguna.
    * *Jawaban:* **B**. SC 2.5.8 ditambahkan pada WCAG 2.2 untuk mencegah salah klik bagi pengguna dengan tremor motorik atau jari besar pada layar sentuh.

---

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario Kasus 1: Notifikasi Toast yang Tak Bersuara**
    * *Problem:* Aplikasi Single Page Application (SPA) menampilkan notifikasi toast dinamis sukses menyimpan data. Elemen toast dibuat dengan:
      ```html
      <div role="status" aria-live="polite">Data berhasil disimpan</div>
      ```
      Namun, pengguna NVDA di Chrome melaporkan bahwa toast tersebut tidak pernah dibacakan sama sekali saat muncul.
    * *Akar Masalah & Solusi:* ARIA live region harus sudah dirender dan berada di dalam DOM **sebelum** teks notifikasi dimasukkan ke dalamnya. Jika kontainer pembungkus dan teks di-mount ke DOM secara bersamaan dalam satu siklus render, browser engine kerap gagal memicu mutasi AXTree. Buat kontainer live region secara statis sejak awal inisialisasi aplikasi, lalu perbarui *text content*-nya saat aksi terjadi.

12. **Skenario Kasus 2: Focus Ring Terpotong Kontainer**
    * *Problem:* Komponen kartu link interaktif memiliki styling outline focus `:focus-visible { outline: 2px solid blue; }`. Namun saat keyboard memfokuskan kartu, outline sisi atas dan bawah tidak terlihat di layar monitor.
    * *Akar Masalah & Solusi:* Elemen parent atau kartu itu sendiri memiliki deklarasi CSS `overflow: hidden;`. Outline visual digambar di luar batas box model elemen sehingga terpotong oleh clipping boundary parent. Solusinya: Ubah CSS menggunakan `outline-offset: -2px;` (menggambar outline ke arah dalam) atau hapus `overflow: hidden` dan gunakan alternatif layout styling modern.

13. **Skenario Kasus 3: Modal Dialog Menutup Sendiri Secara Tak Terduga**
    * *Problem:* Pengguna yang menekan tombol *down arrow* pada custom dropdown di dalam modal dialog mengalami penutupan modal dialog secara mendadak.
    * *Akar Masalah & Solusi:* Event bubbling. Event handler `keydown` pada modal mendengarkan penekanan tombol tertentu (atau event `Escape` yang keliru tertrigger) tanpa melakukan isolasi `e.stopPropagation()`. Komponen modal harus memastikan bahwa event listener keyboard internal hanya menangkap event yang secara spesifik ditujukan untuk fungsionalitas dialog, dan membiarkan event navigasi anak dieksekusi secara terisolasi.

---

### 16. Summary

Mengembangkan antarmuka kelas enterprise yang inklusif bukan sekadar memenuhi checklist audit hukum, melainkan sebuah disiplin rekayasa sistem yang menuntut sinkronisasi presisi antara DOM, CSSOM, dan **Accessibility Tree (AXTree)**. 

Pilar implementasi produksi tingkat lanjut mencakup:
1. **Focus Architecture Determinism:** Menguasai state machine keyboard (*Escape, Tab Trapping, Roving Tabindex, Active Descendant*) yang mencegah pengguna terjebak atau kehilangan konteks.
2. **Native First Hierarchy:** Memprioritaskan elemen semantik native platform (`<dialog>`, `<button>`, `<input>`) sebelum mengadopsi custom ARIA widget yang membutuhkan ribuan baris kode orkestrasi keyboard manual.
3. **Adaptive Visual Engineering:** Menjamin kontras warna adaptif terhadap tema sistem operasi (`forced-colors`), skalabilitas ukuran target sentuh minimal 24x24 CSS piksel (WCAG 2.2), dan mitigasi gerak (*prefers-reduced-motion*).
4. **Resilient Automated Gates:** Memadukan pengujian otomatis axe-core di dalam continuous delivery pipeline untuk menjamin zero regression tanpa mengorbankan performa kecepatan render aplikasi web modern.