# Bab 08 Module 01: Aksesibilitas Digital (a11y) & Desain Inklusif Lanjutan

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 03-Frontend-and-Mobile
* **Jalur Spesialisasi:** UX Design & UI Engineering
* **Nomor Modul:** Bab 08 Module 01
* **Judul Modul:** Aksesibilitas Digital (a11y) & Desain Inklusif Lanjutan
* **Tingkat Kompleksitas:** Advanced / Staff Level
* **Prasyarat Teknis:** Pemahaman mendalam tentang Semantic HTML5, CSS Object Model (CSSOM), Document Object Model (DOM), JavaScript Event Loop, State Management, serta dasar-dasar Assistive Technologies (AT).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Memetakan Web Accessibility Object Model:** Memahami secara mekanistik bagaimana browser mentransformasikan DOM dan CSSOM menjadi Accessibility Tree (a11y tree) untuk dikonsumsi oleh Assistive Technologies (AT).
2. **Menguasai Spesifikasi WAI-ARIA 1.2/1.3 Tingkat Lanjut:** Mengimplementasikan pola interaksi kompleks (Accessible Rich Internet Applications) seperti Compound Widgets, Multi-level Focus Management, dan Live Regions tanpa merusak semantik natif.
3. **Mendesain dan Mengembangkan Sistem Desain Inklusif Multi-Modal:** Membangun antarmuka yang adaptif terhadap input keyboard, screen reader, switch device, dan voice control dengan toleransi kognitif serta kontras visual berbasis WCAG 2.2 level AA/AAA.
4. **Menerapkan Advanced Focus & Interaction Traps:** Mengembangkan custom hooks dan controller native untuk mengelola Focus Trap, Roving Tabindex, dan Virtual Focus tanpa memory leak atau race condition.
5. **Mengintegrasikan Automated Accessibility Testing ke dalam CI/CD:** Mengonfigurasi audit a11y berbasis Axe-core, Playwright, dan dynamic tree snapshotting secara deterministik dalam alur kerja continuous integration.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: The Dual-Tree Architecture

Aksesibilitas bukanlah lapisan kosmetik yang ditambahkan di atas UI (*post-production patch*), melainkan representasi data paralel. Ketika browser merender antarmuka pengguna, browser tidak hanya membangun Render Tree untuk GPU, melainkan membangun **Accessibility Tree (a11y tree)** untuk Platform Accessibility API.

```
                    ┌─────────────────────────┐
                    │       HTML Markup       │
                    └────────────┬────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
        ┌─────────────────┐             ┌─────────────────┐
        │       DOM       │             │      CSSOM      │
        └────────┬────────┘             └────────┬────────┘
                 │                               │
                 ├───────────────────────────────┤
                 ▼                               ▼
        ┌─────────────────┐             ┌─────────────────┐
        │   Render Tree   │             │   a11y Tree     │
        │   (Visual/GPU)  │             │ (Role/State/Val)│
        └────────┬────────┘             └────────┬────────┘
                 ▼                               ▼
        ┌─────────────────┐             ┌─────────────────┐
        │ Display Engine  │             │ Platform API    │
        │  (Pixels/Vsync) │             │ (UIA, AX, ATK)  │
        └─────────────────┘             └────────┬────────┘
                                                 ▼
                                        ┌─────────────────┐
                                        │ Screen Reader / │
                                        │ Switch Devices  │
                                        └─────────────────┘
```

### Prinsip Eksekusi: "First Rule of ARIA"

> *Jika Anda dapat menggunakan elemen HTML5 semantik bawaan yang sudah memiliki atribut dan perilaku bawaan, gunakanlah daripada menggunakan kembali elemen generik dan menambahkan atribut ARIA.*

Menambahkan `role="button"` pada `<div>` tidak memberikan penanganan event keyboard (`Enter`/`Space`), fokus bawaan, disabled state handling, atau touch event synthesis. ARIA murni mengubah semantik pada Accessibility Tree, **bukan perilaku fungsional DOM**.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup sinkronisasi state antara User Interaction, State Management, DOM Mutation, Accessibility Tree, dan Output Assistive Technology:

```
[User Action: Keyboard (Tab/Arrow/Esc)]
                  │
                  ▼
   [Custom Widget Controller (JS)]
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
[State Mutation]      [Focus Manager]
(isOpen: true)        (Move to Active Descendant / Roving Index)
       │                     │
       ├─────────────────────┘
       ▼
[DOM & ARIA Mutation]
  ├── Set aria-expanded="true"
  ├── Set aria-activedescendant="opt-3"
  └── Update aria-live container (jika ada async feedback)
       │
       ▼
[Layout Engine & Platform Accessibility Engine Sync]
  ├── Calculate Computed Accessible Name (AccName 1.2)
  ├── Filter unexposed/hidden nodes (aria-hidden, inert, visibility)
  └── Push Events to OS Accessibility Engine:
        ├── macOS/iOS: NSAccessibility / UIAccessibility
        ├── Windows: UI Automation (UIA) / IAccessible2
        └── Linux: AT-SPI2
       │
       ▼
[Assistive Technology (Screen Reader: NVDA, VoiceOver, JAWS)]
  ├── Intercept OS Event Loop
  ├── Generate Speech/Braille Buffer
  └── Render Feedback Audio/Tactile ke Pengguna
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Accessibility Node Lifecycle & Tree Construction

Accessibility Node dipetakan dari DOM node dengan mempertimbangkan:
* **Role:** Peran elemen (misal: `button`, `combobox`, `dialog`, `treeitem`).
* **Name (Accessible Name):** Dihitung menggunakan algoritma *Accessible Name and Description Computation (AccName 1.2)*. Urutan evaluasi:
  1. `aria-labelledby` (resolusi referensi ID berulang)
  2. `aria-label` (string eksplisit)
  3. Semantik bawaan (misal: elemen `<label>` untuk `<input>`, teks konten internal untuk `<button>`, atribut `alt` untuk `<img>`)
  4. Atribut fallback (misal: `title`, `placeholder` — *tidak disarankan sebagai nama primer*)
* **Description:** Dihitung melalui `aria-describedby` atau `aria-description`.
* **State & Properties:** Nilai boolean atau enumerated seperti `aria-expanded`, `aria-checked`, `aria-disabled`, `aria-selected`, `aria-modal`.

### 2. Atribut `inert` vs `aria-hidden="true"`

* `aria-hidden="true"`: Menghilangkan node dari Accessibility Tree, **tetapi node tetap dapat menerima fokus keyboard** jika memiliki tabindex bawaan atau tabindex >= 0. Hal ini memicu *Focus Trap Anomaly* (pengguna keyboard normal dapat mengaksesnya, pengguna screen reader mengalami kebingungan karena fokus berada pada elemen tak terbaca).
* `inert` (Native HTML attribute):
  1. Menghilangkan elemen dan turunannya dari Accessibility Tree.
  2. Mencegah navigasi fokus keyboard (elemen non-focusable).
  3. Memblokir pointer and touch events.
  4. Mencegah seleksi teks.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Pola Navigasi Keyboard Kompleks: Roving Tabindex vs Virtual Focus

Untuk kumpulan elemen interaktif bersarang (misal: Data Grid, Menu, Combobox), terdapat dua arsitektur navigasi keyboard:

#### Roving Tabindex
Secara dinamis memperbarui atribut `tabindex` dari kumpulan elemen:
* Elemen yang aktif memiliki `tabindex="0"`.
* Seluruh elemen yang tidak aktif memiliki `tabindex="-1"`.
* Ketika pengguna menekan tombol panah (Arrow Keys), JavaScript memindahkan fokus aktual menggunakan `element.focus()`, mengubah indeks elemen sebelumnya menjadi `-1`, dan elemen baru menjadi `0`.
* **Keunggulan:** Kompatibilitas tinggi lintas platform dan Assistive Technology.
* **Kelemahan:** Memerlukan mutasi atribut DOM yang sering saat melakukan navigasi dataset besar.

#### Virtual Focus (`aria-activedescendant`)
Fokus DOM aktual tetap berada pada elemen container (misal: `input` atau `ul` ber-tabindex `0`):
* Container memantau event penekanan tombol (`keydown`).
* Kontainer memperbarui atribut `aria-activedescendant="id-anak-yang-aktif"`.
* Browser memicu event mutasi fokus virtual ke Assistive Technology tanpa memindahkan fokus native DOM.
* **Keunggulan:** Kinerja rendering tinggi; meminimalkan layout shift dan reflow fokus.
* **Kelemahan:** Styling kursor/fokus visual harus dikelola manual via CSS pseudo-class/attribute selector.

### 2. Live Regions: Mekanika Asinkronitas dan Politeness Levels

`aria-live` memberitahukan assistive technologies untuk menyuarakan perubahan DOM yang dinamis tanpa memindahkan fokus pengguna.

| Nilai Atribut | Antrian TTS (Text-to-Speech) | Karakteristik Perilaku | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| `off` (Default) | Diabaikan | Perubahan DOM tidak dibacakan. | Perubahan konten background standar. |
| `polite` | Antrian Idle | Menunggu pengguna selesai berbicara atau istirahat mengetik. | Notifikasi toast, pembaruan keranjang belanja. |
| `assertive` | Preemptif (Interupsi) | Menginterupsi langsung audio buffer saat ini. | Error validasi sistem kritis, session timeout warning. |

*Atribut Komplementer:*
* `aria-atomic="true"`: Memaksa screen reader membaca seluruh kontainer wilayah live secara utuh saat terjadi mutasi kecil pada anak DOM-nya, bukan hanya membaca fragmen teks yang berubah.
* `aria-relevant="additions text"`: Menentukan jenis mutasi DOM yang memicu event.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Accessible Modal Dialog System berbasis Typescript/Vanilla JS yang mengimplementasikan:
1. Native `inert` control pada root elemen aplikasi untuk mengisolasi background.
2. Focus trapping terdistribusi dengan restorasi elemen fokus awal.
3. Event listener terisolasi untuk penekanan tombol `Escape`.
4. Semantik WAI-ARIA 1.2 modal dialog.

```typescript
// AccessibleDialog.ts
export interface DialogOptions {
  triggerElement: HTMLElement;
  dialogElement: HTMLElement;
  appRootElement: HTMLElement;
  closeButtonSelector: string;
}

export class AccessibleDialog {
  private triggerElement: HTMLElement;
  private dialogElement: HTMLElement;
  private appRootElement: HTMLElement;
  private closeButton: HTMLElement | null;
  private previouslyFocusedElement: HTMLElement | null = null;
  private isOpen: boolean = false;

  constructor(options: DialogOptions) {
    this.triggerElement = options.triggerElement;
    this.dialogElement = options.dialogElement;
    this.appRootElement = options.appRootElement;
    this.closeButton = this.dialogElement.querySelector(options.closeButtonSelector);

    this.init();
  }

  private init(): void {
    // Pastikan modal dialog memiliki role dan state yang tepat
    this.dialogElement.setAttribute('role', 'dialog');
    this.dialogElement.setAttribute('aria-modal', 'true');
    this.dialogElement.setAttribute('hidden', '');

    // Bindings
    this.triggerElement.addEventListener('click', () => this.open());
    if (this.closeButton) {
      this.closeButton.addEventListener('click', () => this.close());
    }
    this.dialogElement.addEventListener('keydown', (e) => this.handleKeyDown(e));
  }

  public open(): void {
    if (this.isOpen) return;

    this.previouslyFocusedElement = document.activeElement as HTMLElement;
    this.isOpen = true;

    // 1. Tampilkan Dialog
    this.dialogElement.removeAttribute('hidden');

    // 2. Terapkan inert pada main application tree untuk mengisolasi fokus & aksesibilitas
    this.appRootElement.setAttribute('inert', '');

    // 3. Pindahkan fokus ke dalam modal dialog
    this.setInitialFocus();
  }

  public close(): void {
    if (!this.isOpen) return;

    this.isOpen = false;

    // 1. Bersihkan inert
    this.appRootElement.removeAttribute('inert');

    // 2. Sembunyikan Dialog
    this.dialogElement.setAttribute('hidden', '');

    // 3. Kembalikan fokus ke trigger element
    if (this.previouslyFocusedElement && typeof this.previouslyFocusedElement.focus === 'function') {
      this.previouslyFocusedElement.focus();
    }
  }

  private setInitialFocus(): void {
    const focusableSelectors = [
      'button:not([disabled])',
      '[href]',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(', ');

    const focusableElements = Array.from(
      this.dialogElement.querySelectorAll<HTMLElement>(focusableSelectors)
    );

    if (focusableElements.length > 0) {
      focusableElements[0].focus();
    } else {
      // Fallback jika tidak ada elemen interaktif, fokuskan ke wrapper dialog
      this.dialogElement.setAttribute('tabindex', '-1');
      this.dialogElement.focus();
    }
  }

  private handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close();
      return;
    }

    if (event.key === 'Tab') {
      // Fallback trapping jika platform belum mendukung atribut native inert secara sempurna
      this.trapFocus(event);
    }
  }

  private trapFocus(event: KeyboardEvent): void {
    const focusables = this.dialogElement.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    
    if (focusables.length === 0) return;

    const firstElement = focusables[0];
    const lastElement = focusables[focusables.length - 1];

    if (event.shiftKey) {
      if (document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      }
    } else {
      if (document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah bedah struktural kelas `AccessibleDialog`:

* **Baris 24–27 (`this.dialogElement.setAttribute(...)`):**
  * `role="dialog"`: Mengumumkan ke assistive technologies bahwa komponen ini adalah sub-window interaktif terpisah.
  * `aria-modal="true"`: Memberitahu browser a11y engine bahwa elemen di luar kontainer dialog tidak boleh diperhitungkan dalam traversal screen reader (dukungan legacy sebelum spesifikasi `inert`).
  * `hidden`: Menghentikan rendering visual dan menghapus elemen dari a11y tree saat sedang inaktif.
* **Baris 42 (`this.previouslyFocusedElement = document.activeElement as HTMLElement`):** Menyimpan snapshot node fokus saat ini sebelum konteks dialihkan. Kegagalan menyimpan referensi ini menyebabkan *Focus Loss Pitfall*, di mana saat modal ditutup, fokus akan kembali secara acak ke `<body>`, memaksa pengguna keyboard mengulang navigasi dari awal halaman.
* **Baris 48 (`this.appRootElement.setAttribute('inert', '')`):** Fitur krusial. Ini secara otomatis melumpuhkan seluruh pointer, seleksi visual, dan navigasi Tab di seluruh aplikasi induk tanpa perlu memanipulasi `tabindex` setiap elemen individu di halaman luar modal.
* **Baris 63–65 (`this.previouslyFocusedElement.focus()`):** Eksekusi pemulihan fokus (Focus Restoration) deterministik saat modal ditutup.
* **Baris 97–100 (`event.key === 'Escape'`):** Memenuhi WCAG 2.2 Success Criterion 2.1.2 (No Keyboard Trap). Pengguna harus selalu diberikan rute keluar yang konsisten menggunakan tombol standar keyboard `Escape`.
* **Baris 112–126 (`trapFocus` edge routing):** Algoritma kompensasi keyboard trapping fallback. Jika pengguna berada di `lastElement` dan menekan `Tab`, fokus diarahkan ke `firstElement`. Jika berada di `firstElement` dan menekan `Shift + Tab`, fokus ditarik mundur ke `lastElement`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: Financial Core Banking Transaction Data Table

Sebuah perbankan multinasional memiliki antarmuka back-office bernama *ApexTrade* yang digunakan oleh ribuan operator, termasuk staf penyandang disabilitas low vision dan motorik parsial. 

#### Permasalahan Utama:
1. **Navigasi Tab Fatigue:** Halaman memiliki Data Table dengan 100 baris transaksi. Setiap baris memiliki 5 tombol aksi (`Lihat`, `Unduh`, `Setujui`, `Tolak`, `Log`). Untuk melompat dari tabel ke bagian formulir di bawahnya, pengguna keyboard harus menekan tombol `Tab` sebanyak 500 kali (100 baris × 5 tombol).
2. **Dynamic Stock Ticker Polling:** Sistem memperbarui kurs mata uang dan harga saham setiap 3 detik. Developer junior memasang atribut `aria-live="assertive"` pada kontainer harga. Hasilnya: Screen reader terus menerus memotong suara pembacaan dokumen dan membacakan kurs mata uang setiap 3 detik tanpa henti, merusak operasional pengguna tunanetra.
3. **Modal Form Broken Semantics:** Ketika modal konfirmasi transaksi muncul, screen reader tetap membaca transaksi di latar belakang karena pengembang hanya menggunakan CSS `position: fixed; z-index: 9999` tanpa mengisolasi a11y tree.

#### Target Rekayasa Sistem:
* Menghilangkan *Tab Fatigue* dengan mengonversi Data Table menggunakan pola **WAI-ARIA Data Grid Roving Tabindex Composite Widget**. Pengguna cukup menekan `Tab` sekali untuk masuk ke Grid, lalu menavigasi baris dan kolom menggunakan tombol panah (`Arrow Keys`), kemudian menekan `Tab` sekali lagi untuk keluar dari Grid secara langsung.
* Mengisolasi live stream ticker menggunakan decoupled buffer berbasis `aria-live="polite"` yang hanya membacakan perubahan ketika pengguna secara spesifik meminta ringkasan (User-Polled Live Announcer).
* Membangun Focus Boundary and Isolation menggunakan native `inert` controller.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi Grid Roving Tabindex untuk perbankan skala enterprise menggunakan TypeScript:

```typescript
// AccessibleDataGrid.ts
export interface GridCellCoordinate {
  rowIndex: number;
  colIndex: number;
}

export class AccessibleDataGrid {
  private gridElement: HTMLElement;
  private rows: HTMLElement[] = [];
  private currentCoords: GridCellCoordinate = { rowIndex: 0, colIndex: 0 };
  private cellMatrix: HTMLElement[][] = [];

  constructor(gridElement: HTMLElement) {
    this.gridElement = gridElement;
    this.init();
  }

  private init(): void {
    // Pasang role grid
    this.gridElement.setAttribute('role', 'grid');
    this.gridElement.setAttribute('aria-rowcount', '0'); // Akan diupdate

    this.buildMatrix();
    this.bindEvents();
    this.syncTabIndices();
  }

  private buildMatrix(): void {
    this.rows = Array.from(this.gridElement.querySelectorAll('[data-grid-row]'));
    this.gridElement.setAttribute('aria-rowcount', this.rows.length.toString());

    this.cellMatrix = this.rows.map((row, rIdx) => {
      row.setAttribute('role', 'row');
      row.setAttribute('aria-rowindex', (rIdx + 1).toString());

      const cells = Array.from(row.querySelectorAll<HTMLElement>('[data-grid-cell]'));
      cells.forEach((cell, cIdx) => {
        cell.setAttribute('role', 'gridcell');
        cell.setAttribute('aria-colindex', (cIdx + 1).toString());
      });
      return cells;
    });
  }

  private syncTabIndices(): void {
    this.cellMatrix.forEach((row, rIdx) => {
      row.forEach((cell, cIdx) => {
        if (rIdx === this.currentCoords.rowIndex && cIdx === this.currentCoords.colIndex) {
          cell.setAttribute('tabindex', '0');
        } else {
          cell.setAttribute('tabindex', '-1');
        }
      });
    });
  }

  private bindEvents(): void {
    this.gridElement.addEventListener('keydown', (e: KeyboardEvent) => this.handleKeyDown(e));
    this.gridElement.addEventListener('click', (e: MouseEvent) => this.handleClick(e));
  }

  private handleClick(event: MouseEvent): void {
    const target = (event.target as HTMLElement).closest<HTMLElement>('[data-grid-cell]');
    if (!target) return;

    for (let r = 0; r < this.cellMatrix.length; r++) {
      const c = this.cellMatrix[r].indexOf(target);
      if (c !== -1) {
        this.currentCoords = { rowIndex: r, colIndex: c };
        this.syncTabIndices();
        target.focus();
        break;
      }
    }
  }

  private handleKeyDown(event: KeyboardEvent): void {
    const { rowIndex, colIndex } = this.currentCoords;
    let handled = false;

    switch (event.key) {
      case 'ArrowDown':
        if (rowIndex < this.cellMatrix.length - 1) {
          this.currentCoords.rowIndex++;
          handled = true;
        }
        break;
      case 'ArrowUp':
        if (rowIndex > 0) {
          this.currentCoords.rowIndex--;
          handled = true;
        }
        break;
      case 'ArrowRight':
        if (colIndex < this.cellMatrix[rowIndex].length - 1) {
          this.currentCoords.colIndex++;
          handled = true;
        }
        break;
      case 'ArrowLeft':
        if (colIndex > 0) {
          this.currentCoords.colIndex--;
          handled = true;
        }
        break;
      case 'Home':
        if (event.ctrlKey) {
          this.currentCoords = { rowIndex: 0, colIndex: 0 };
        } else {
          this.currentCoords.colIndex = 0;
        }
        handled = true;
        break;
      case 'End':
        if (event.ctrlKey) {
          this.currentCoords = {
            rowIndex: this.cellMatrix.length - 1,
            colIndex: this.cellMatrix[this.cellMatrix.length - 1].length - 1
          };
        } else {
          this.currentCoords.colIndex = this.cellMatrix[rowIndex].length - 1;
        }
        handled = true;
        break;
      default:
        break;
    }

    if (handled) {
      event.preventDefault();
      this.syncTabIndices();
      const targetCell = this.cellMatrix[this.currentCoords.rowIndex][this.currentCoords.colIndex];
      targetCell.focus();
    }
  }
}
```

```html
<!-- Markup Penggunaan Data Grid -->
<div id="transaction-grid" aria-label="Daftar Transaksi Perbankan">
  <div data-grid-row>
    <div data-grid-cell>TX-9841</div>
    <div data-grid-cell>PT Solusi Digital</div>
    <div data-grid-cell>Rp 250.000.000</div>
    <div data-grid-cell><button type="button">Approve</button></div>
  </div>
  <div data-grid-row>
    <div data-grid-cell>TX-9842</div>
    <div data-grid-cell>CV Maju Lancar</div>
    <div data-grid-cell>Rp 12.500.000</div>
    <div data-grid-cell><button type="button">Approve</button></div>
  </div>
</div>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Pendekatan Focus Management | Keuntungan Performa | Aksesibilitas Assistive Tech | Kerumitan Kode | Dampak Performa DOM (DOM Thrashing) |
| :--- | :--- | :--- | :--- | :--- |
| **Native Focus Navigation** (Default Tab Order) | Zero Overhead JS. Native browser caching. | Sangat tinggi untuk form sederhana. Sangat buruk untuk complex matrix (Tab Fatigue). | Nol (`O(1)` complexity). | Nol. |
| **Roving Tabindex** | Kontrol presisi. AT mengumumkan posisi tepat melalui fokus native DOM. | Sempurna. Didukung 100% oleh NVDA, JAWS, VoiceOver, Android TalkBack. | Menengah. Perlu tracking matriks 2 dimensi. | Rendah ke Menengah (Mutasi atribut `tabindex` saat panah keyboard ditekan). |
| **Virtual Focus (`aria-activedescendant`)** | Sangat cepat. Tidak ada mutasi fokus DOM native. Sangat baik untuk ribuan baris list. | Variatif. Bergantung implementasi VoiceOver/TalkBack pada browser mobile. | Tinggi. Membutuhkan sinkronisasi ID dinamis dan CSS rendering state. | Nol. Hanya mutasi atribut string pada node kontainer induk. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Screen Reader Virtual Cursor vs Browser Event Loop Trap
Pada sistem desktop seperti Windows (NVDA/JAWS), terdapat mode **Browse Mode** (navigasi virtual AT menggunakan panah atas/bawah) dan **Focus/Forms Mode** (input passthrough langsung ke browser).
* *Pitfall:* Ketika Anda membuat custom widget berbasis `role="application"`, NVDA akan mematikan semua shortcut keyboard native-nya (misal: tombol 'H' untuk melompat antar Heading). Jika aplikasi web Anda tidak menangani semua shortcut dengan sempurna, pengguna akan terjebak dan kehilangan kontrol navigasi.
* *Mitigasi:* Jangan pernah gunakan `role="application"` pada level kontainer besar (seperti `<body>` atau `<main>`). Terapkan pola ARIA spesifik (`role="grid"`, `role="listbox"`) hanya pada kontainer terkecil yang membutuhkannya.

### 2. Live Region Announce Collisions
Jika dua pembaruan `aria-live="polite"` terjadi dalam window waktu di bawah 100ms, beberapa browser WebKit (Safari/VoiceOver) akan membuang pesan pertama dan hanya menyuarakan pesan kedua (*Announcement Dropping*).
* *Mitigasi:* Gunakan antrean terkelola (*Speech Dispatcher Queue*) dengan debounce minimal 150ms antar pengumuman teks live region.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menggunakan `aria-label` pada elemen non-interactive tanpa Role yang valid
```html
<!-- SALAH: Div tidak memiliki semantik bawaan; aria-label akan diabaikan oleh banyak screen reader -->
<div aria-label="Total Pembayaran">Rp 500.000</div>

<!-- BENAR: Menggunakan semantik teks yang valid atau menambahkan role landmark -->
<div role="region" aria-label="Total Pembayaran">Rp 500.000</div>
<!-- ATAU LEBIH BAIK TANPA ARIA: -->
<section aria-label="Total Pembayaran"><p>Rp 500.000</p></section>
```

### Kesalahan Fatal 2: Menghancurkan Focus Ring CSS
```css
/* SALAH: Menghilangkan indikator fokus sepenuhnya (Pelanggaran Kritis WCAG 2.4.7) */
*:focus {
  outline: none;
}

/* BENAR: Mengganti dengan indikator kustom kontras tinggi menggunakan :focus-visible */
*:focus:not(:focus-visible) {
  outline: none;
}
*:focus-visible {
  outline: 3px solid #005fcc;
  outline-offset: 2px;
}
```

### Kesalahan Fatal 3: Tautan Kosong Berbasis Ikon
```html
<!-- SALAH: Screen reader membacakan "Link" tanpa makna fungsional -->
<a href="/settings"><svg class="icon-gear"></svg></a>

<!-- BENAR: Menyediakan Visually Hidden text atau aria-label terstandarisasi -->
<a href="/settings" aria-label="Pengaturan Akun">
  <svg class="icon-gear" aria-hidden="true" focusable="false"></svg>
</a>
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Visually Hidden Utility (Bukan `display: none` atau `visibility: hidden`):**
   Konten yang disembunyikan visual namun harus dibaca oleh screen reader harus menggunakan clipping layout:
   ```css
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
   ```
2. **Kepatuhan Rasio Kontras Berdasarkan WCAG 2.2:**
   * Teks Standar (< 18pt normal atau < 14pt bold): Rasio kontras minimal **4.5:1** terhadap latar belakang (Level AA).
   * Teks Besar (>= 18pt normal atau >= 14pt bold) dan Elemen UI Interaktif (Border input, Icon Button): Rasio kontras minimal **3:1** (Level AA).
   * Level AAA: Rasio **7:1** untuk teks standar dan **4.5:1** untuk teks besar.
3. **Target Sentuh Minimum (WCAG 2.2 Target Size - SC 2.5.8):**
   Target interaktif harus memiliki ukuran minimal **24x24 CSS pixels** atau memiliki jarak kompensasi (spacing) yang mencegah overlapping klik tidak disengaja. Untuk standar mobile primer (Apple HIG / Android Material), standarnya adalah **44x44 pt** / **48x48 dp**.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

Pola mutasi Accessibility Tree yang buruk dapat menyebabkan kinerja anjlok drastis (*Accessibility Tree Churn*):

1. **Batching DOM Attributes Mutation:** Jangan mutasi `aria-*` attributes satu per satu di dalam loop render besar. Modifikasi atribut ARIA memicu sinkronisasi thread OS Accessibility Engine. Gunakan `DocumentFragment` atau batch mutations.
2. **Garbage Collection pada Focus Trap Listeners:** Hapus global `keydown` event listener dari memory setiap kali modal ditutup. Kegagalan melepaskan handler yang menutup closure dialog akan menahan referensi seluruh detached DOM tree di memori (*Zombie Node Memory Leak*).
3. **CSS Content-Visibility Alert:** Hati-hati saat menggunakan `content-visibility: auto` untuk virtualisasi rendering. Konten yang berada di luar viewport akan dihilangkan dari rendering tree visual **dan Accessibility Tree**, sehingga Screen Reader tidak dapat melakukan search-in-page (Ctrl+F) terhadap konten tersebut.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Accessibility-Based Phishing & Clickjacking:**
   * Elemen tersembunyi dengan `.sr-only` yang disisipi teks berbahaya dapat menipu pengguna tunanetra untuk mengeklik link malicious. Sanitasi semua input string yang disuntikkan ke dalam `aria-label`, `aria-description`, dan teks Visually Hidden menggunakan parser anti-XSS terpercaya (misal: DOMPurify).
2. **Exposing Sensitive Data via Accessibility Tree:**
   * Atribut `aria-label` sering kali tidak terlihat secara visual di layar pengguna. Pengembang sering tidak sengaja mengekspos token internal, status transaksi rahasia, atau PII (Personally Identifiable Information) ke dalam atribut ARIA untuk kebutuhan internal tracking. 
   * Ingat: **Accessibility Tree adalah surface publik**. Siapa pun dapat menginspeksi nilai ARIA menggunakan Chrome DevTools Accessibility Panel atau OS accessibility reader bridge.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Automated Unit/Integration Pipeline dengan Axe-Core

Integrasi audit deterministik dalam Playwright E2E:

```typescript
// tests/a11y.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Audit Aksesibilitas Halaman Checkout', () => {
  test('Harus memenuhi standar WCAG 2.2 Level AA tanpa pelanggaran kritis', async ({ page }) => {
    await page.goto('/checkout');
    await page.waitForSelector('#transaction-grid');

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .disableRules(['color-contrast']) // Gunakan hanya jika diuji via sistem chromatic visual terpisah
      .analyze();

    // Verifikasi bahwa violation list bernilai kosong
    expect(accessibilityScanResults.violations).toEqual([]);
  });
});
```

### Telemetri & User Agent Metrics
Jangan pernah mencoba mendeteksi keberadaan screen reader via JavaScript (misal: mendeteksi flag khusus). Fitur deteksi langsung semacam ini sengaja diblokir oleh vendor browser untuk mencegah *Fingerprinting Vector* dan diskriminasi antarmuka. 

Ukur performa a11y secara etis melalui:
* Telemetri navigasi keyboard: Ukur rasio event `keydown: Tab` vs `mousedown` untuk memahami persentase power keyboard user.
* Evaluasi `window.matchMedia('(prefers-reduced-motion: reduce)')` dan `window.matchMedia('(prefers-contrast: more)')` untuk melacak preferensi ergonomis pengguna secara agregat.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Gunakan HTML Semantik Dulu:** `<button>` selalu mengalahkan `<div role="button">`.
* **AccName Resolution Order:** `aria-labelledby` > `aria-label` > Native Semantic Content > Fallbacks.
* **Modal Dialog Checklist:**
  1. Pasang `role="dialog"` dan `aria-modal="true"`.
  2. Berikan Accessible Name via `aria-labelledby="title-id"`.
  3. Berikan `inert` pada node aplikasi