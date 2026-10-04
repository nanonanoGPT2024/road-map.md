# BAB 05: Quiz, Challenge, & Knowledge Check
**Component Primitives & Headless UI Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Inversion of Control (IoC) & Separation of Concerns
Jelaskan secara mendalam bagaimana paradigma *Headless UI* mengimplementasikan prinsip *Inversion of Control* (IoC) dalam arsitektur design system modern. Bedakan batas tanggung jawab (*boundaries*) antara *state machine/behavioral logic*, *accessibility (a11y) tree mapping*, dan *render layer/styling*. Mengapa memisahkan ketiga aspek ini secara arsitektural krusial untuk mencegah degradasi performa dan *design debt* pada monorepo skala enterprise?

### Soal 1.2: Prop Getters vs. Compound Components Pattern
Bandingkan pola arsitektur **Prop Getters Pattern** (seperti yang digunakan pada Downshift/Kent C. Dodds pattern) dengan **Compound Components Pattern berbasis Context & Slot** (seperti pada Radix UI / Ark UI). 
- Analisis bagaimana masing-masing pola menangani komposisi struktur DOM, transmisi state implisit vs eksplisit, dan resolusi konflik atribut (misalnya *event handler composition* `onClick` bawaan vs `onClick` konsumen).
- Kapan salah satu pola lebih superior dibanding yang lain dalam konteks extensibility komponen enterprise?

### Soal 1.3: Polymorphism: Slot Pattern (`asChild`) vs. Polymorphic `as` Prop
Dalam implementasi component primitive, pola `as` prop tradisional (`<Button as={Link} href="/home" />`) kerap memicu kompleksitas inferensi TypeScript yang ekstrem (menghasilkan *type-instantiation depth limits*) dan inkonsistensi runtime DOM footprint. 
- Bedah mekanisme kerja internal pola **Slot Pattern** (pendekatan `asChild` berbasis kloning elemen/merging props).
- Jelaskan bagaimana Slot Pattern mengatasi kelemahan inferensi tipe TypeScript dan menjaga integritas semantik elemen DOM tanpa menyuntikkan node wrapper tambahan (*redundant wrapper nodes*).

### Soal 1.4: Aksesibilitas Deterministik & ARIA State Synchronization
Mengapa manajemen aksesibilitas (WAI-ARIA 1.2/APG) pada komponen primitive harus bersifat deterministik dan dikontrol langsung oleh internal state engine? 
- Uraikan risiko teknis jika developer styling/konsumen diizinkan memanipulasi atribut ARIA secara manual (misalnya `aria-expanded`, `aria-controls`, `aria-activedescendant`).
- Bagaimana primitive headless menjamin sinkronisasi real-time antara state JavaScript (misal: open/closed, active index) dengan *Accessibility Tree* browser pada level thread rendering?

### Soal 1.5: Uncontrolled-by-Default, Controlled-when-Needed
Salah satu prinsip utama pembuatan primitive headless adalah kapabilitas transisi mulus antara status *uncontrolled* (internal state engine) dan *controlled* (state di-drive via external props seperti `value` dan `onChange`).
- Jelaskan mekanisme rancang bangun hook/utility primitif (sering disebut `useControllableState`) yang mencegah anti-pattern *state synchronization thrashing*.
- Mengapa *state reflection* via `useEffect` merupakan anti-pattern dalam konteks ini, dan bagaimana primitive menangani perubahan nilai tanpa memicu *tearing* atau *unnecessary re-renders*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Event Handler Chaining & `event.defaultPrevented`
Dalam headless architecture, konsumen komponen sering kali perlu menyematkan *custom logic* pada event yang sama dengan yang dibutuhkan oleh internal behavioral engine primitive (contoh: membatalkan aksi penutupan *Dropdown* saat event `onKeyDown` Escape ditekan).
- Tuliskan dan jelaskan implementasi internal fungsi utility `composeEventHandlers(originalHandler, ourHandler, { checkForDefaultPrevented })`.
- Analisis urutan eksekusi (*execution pipeline*) dan jelaskan bagaimana primitive menghormati `event.preventDefault()` yang dipanggil oleh konsumen tanpa merusak internal state transition.

### Soal 2.2: Focus Trapping, Inert DOM, dan Micro-Frontend Portals
Pada komponen primitive seperti Modal Dialog atau Drawer yang me-*render* kontennya ke DOM Node eksternal via Portal:
- Bagaimana mekanisme kerja *Focus Trap* modern dalam menangani siklus navigasi Tab dan Shift+Tab agar tidak "bocor" (*leak*) ke elemen root dokumen?
- Analisis kendala internal yang muncul jika dokumen memiliki implementasi multi-layered modal (nested dialogs) atau lingkungan Micro-Frontend (MFE) yang menyuntikkan subtree independen.
- Mengapa API browser modern seperti atribut `inert` kini lebih dipilih dibandingkan manipulasi manual `tabIndex="-1"` pada semua elemen saudara (*sibling nodes*) di Accessibility Tree?

### Soal 2.3: Positioning Engine & Collision Detection (Floating Primitives)
Komponen seperti Popover, Tooltip, dan Dropdown mengandalkan headless positioning engine (misalnya Floating UI) untuk kalkulasi koordinat geometris.
- Bagaimana positioning engine menghitung posisi optimal pada viewport yang padat (*boundary collisions*) menggunakan kombinasi strategi `flip`, `shift`, dan `virtual padding`?
- Debug skenario di mana elemen popover bergetar (*flickering/jittering*) terus menerus secara tak terbatas saat di-scroll di dekat viewport boundary. Apa akar masalah matematis/siklus render-nya dan bagaimana cara mitigasinya?

### Soal 2.4: SSR Hydration Mismatch & Deterministic ID Generation
Primitive yang mengandalkan hubungan semantik antar elemen (misalnya menghubungkan `<label for="...">` dengan `<input id="...">`, atau `aria-labelledby` dengan konten Dialog) membutuhkan ID yang konsisten antara Server-Side Rendering (SSR) dan Client-Side Hydration.
- Mengapa pendekatan `Math.random()` atau counter global linier sederhana (`idCounter++`) memicu *React Hydration Mismatch* fatal pada arsitektur modern (seperti Next.js App Router / SSR Streaming)?
- Analisis cara kerja internal hook `useId` bawaan React atau algoritma *tree-based ID prefixing* dalam menjamin determinisme identifier tanpa memerlukan pertukaran state jaringan tambahan.

### Soal 2.5: Virtualization & Keyboard Navigation Engine Coupling
Ketika membangun headless primitive `Combobox` atau `Autocomplete` dengan 50.000 items yang di-virtualisasi (hanya me-render ~10 DOM nodes visible):
- Mengapa navigasi keyboard standar berbasis pemindahan fokus DOM riil (`element.focus()`) gagal total pada skenario ini?
- Bedah implementasi teknis pola `aria-activedescendant` yang dipadukan dengan *virtualizer offset calculation*.
- Bagaimana primitive headless mendeteksi bahwa item yang dipilih sedang berada di luar *render buffer window* dan secara sinkron memerintahkan virtualizer untuk melakukan scrolling tanpa memicu *layout thrashing*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Focus Management & DOM Thrashing pada Mega-Menu E-Commerce Multi-Level
*Konteks*: Platform e-commerce global mengimplementasikan Mega-Menu headless dengan ratusan kategori dan ribuan sub-kategori bertingkat. Pengguna melaporkan lag ekstrem (Frame Drop hingga <15 FPS) saat bernavigasi menggunakan keyboard (Arrow Keys). Profiling performance via Chrome DevTools Performance panel menunjukkan:
1. Long Task (>180ms) terjadi setiap kali `keydown` dieksekusi.
2. 80% waktu Long Task habis pada fase *Recalculate Style* dan *Layout*, yang dipicu berulang kali oleh baris kode internal primitive: `node.getBoundingClientRect()` dan `document.activeElement.focus()`.
3. Screen reader (NVDA/VoiceOver) tertinggal jauh dalam mengumumkan elemen yang sedang aktif, memicu pembacaan teks yang tumpang tindih.

*Pertanyaan Diagnostik*:
1. Identifikasi secara tepat akar masalah (*root cause*) dari fenomena *forced synchronous layout* (layout thrashing) pada arsitektur mega-menu tersebut.
2. Rancang ulang strategi focus management dan kalkulasi dimensi menu menggunakan pendekatan headless murni. Kapan informasi geometri DOM boleh dibaca, dan bagaimana Anda mengabstraksi navigasi spasial keyboard menggunakan model data linear/matriks virtual alih-alih melakukan querying DOM secara langsung?
3. Tuliskan arsitektur perbaikan throttling/debouncing navigasi aksessibilitas agar screen reader tidak mengalami event queue saturation.

---

### Skenario B: Hydration Desync & Race Condition pada Nested Micro-Frontend Dialogs
*Konteks*: Suatu dashboard perbankan enterprise terdiri dari Host Container dan tiga Micro-Frontend (MFE) yang diintegrasikan via Webpack Module Federation. Masing-masing MFE membungkus headless primitive modal yang me-render konten ke DOM Portal bersama (`#global-portal-root`).
Terjadi insiden kritis di produksi:
- Ketika MFE Keuangan membuka Modal konfirmasi transfer uang di atas Modal navigasi Host yang sedang terbuka, terjadi *hydration mismatch warning* di konsol.
- Saat Modal konfirmasi ditutup, fokus keyboard bukan kembali ke elemen pemicu (*trigger element*) di MFE Keuangan, melainkan terlempar ke `document.body` (Focus Trap Host ikut hancur).
- Mengklik di luar area modal (*pointer-down-outside*) pada modal kedua justru menutup kedua modal sekaligus secara instan (*click-through ghost dismissal*).

*Pertanyaan Diagnostik*:
1. Mengapa keberadaan satu shared portal root DOM (`#global-portal-root`) memicu konflik event bubbling dan *pointer-down-outside detection* pada arsitektur MFE bertingkat?
2. Bagaimana mekanisme isolasi *Focus Scope Stack* seharusnya diimplementasikan pada level primitive agar tumpukan (stack) modal dapat dipertahankan secara LIFO (Last-In-First-Out) lintas boundary aplikasi/iframe/MFE?
3. Rancang strategi pencegahan *ghost click / pointer capture bleeding* ketika backdrop terluar di-unmount dari DOM saat event `pointerup` belum selesai diproses oleh browser.

---

### Skenario C: Architecture & Trade-Off System: Custom Hooks Engine vs. Component-Based Primitive Framework
*Konteks*: Perusahaan SaaS skala global sedang mendesain ulang fondasi Component Library internal mereka yang melayani 40+ tim produk independen. Tim Core Design System terpecah menjadi dua kubu arsitektur:
- **Kubu A (Hook-Centric)**: Menganjurkan penyediaan hooks murni (seperti React Aria Hooks). Pendapat: Memberikan kebebasan 100% pada struktur HTML/JSX konsumen, bundle size minimum untuk aplikasi non-UI, dan tidak memaksakan opini DOM tree.
- **Kubu B (Component/Slot-Centric)**: Menganjurkan penyediaan unstyled compound primitives dengan Slot mechanism (seperti Radix UI / Ark UI). Pendapat: Hooks murni terlalu rentan disalahgunakan (*developer-error prone*), menyebabkan tim produk lupa menyambungkan atribut a11y vital, dan meningkatkan code verbosity hingga 4x lipat di sisi aplikasi konsumen.

*Pertanyaan Diagnostik*:
1. Buat matriks evaluasi perbandingan teknis komprehensif antara kedua pendekatan tersebut berdasarkan 5 kriteria:
   - *Accessibility Guarantee & Compliance Enforceability*
   - *Developer Experience (DX) & Ergonomics*
   - *Bundle Size Footprint & Tree-Shaking Efficiency*
   - *Cross-Framework Reusability (misal: adaptasi ke Vue/Svelte/Solid)*
   - *Maintenance Overhead pada Core DS Team*
2. Dari perspektif Principal Engineer, rumuskan keputusan arsitektur hibrida atau deterministik terbaik untuk perusahaan tersebut, termasuk panduan aturan kapan tim produk boleh turun ke level Hook dan kapan wajib menggunakan Primitive Component.

---

## 4. Chapter Challenge

### Tantangan Praktis: Merancang Headless Accessible Combobox Primitive Engine dari Nol (Zero-Dependency)

#### Problem Statement
Sebagian besar library UI pihak ketiga gagal mengabstraksi komponen **Combobox** dengan benar. Komponen Combobox enterprise membutuhkan kombinasi state yang rumit: manipulasi teks input, sinkronisasi navigasi panah keyboard, penyaringan data asinkron, kalkulasi ARIA 1.2 `role="combobox"` yang tepat, dan komposisi DOM yang fleksibel tanpa mengorbankan aksesibilitas.

Anda diminta mengimplementasikan arsitektur headless primitive untuk **Combobox Engine** menggunakan TypeScript murni dan React (tanpa library headless eksternal seperti Radix, HeadlessUI, atau Downshift).

#### Requirements
1. **Core Architecture**:
   - Pisahkan logika ke dalam custom hook engine: `useCombobox<T>({ items, itemToString, onSelectedItemChange, ... })`.
   - Sediakan komponen pembungkus dengan pola Compound Components + Slot Pattern (`Combobox.Root`, `Combobox.Input`, `Combobox.Trigger`, `Combobox.Content`, `Combobox.Item`).
2. **Behavioral & Accessibility (WAI-ARIA 1.2 APG)**:
   - Input wajib memiliki atribut dinamis: `role="combobox"`, `aria-autocomplete="list"`, `aria-expanded`, `aria-controls`, dan `aria-activedescendant`.
   - Penekanan tombol keyboard harus presisi:
     - `ArrowDown` / `ArrowUp`: Melintasi opsi aktif tanpa memindahkan kursor input teks, mengubah `aria-activedescendant` ke ID item yang relevan.
     - `Enter`: Memilih item yang sedang aktif via navigasi panah, memanggil `onSelectedItemChange`, dan menutup list.
     - `Escape`: Menutup dropdown list. Jika list sudah tertutup, membersihkan nilai input.
     - `Home` / `End`: Bernavigasi langsung ke item pertama/terakhir saat dropdown terbuka (jika fokus sedang di virtual list).
3. **Composition Mechanics**:
   - Mendukung pola `asChild` pada `Combobox.Trigger` dan `Combobox.Item` menggunakan mekanisme kloning elemen dengan integrasi refs yang aman (*merging refs*).
   - Menggunakan utility `composeEventHandlers` internal untuk mencegah penimpaan (*overwriting*) custom event handler milik konsumen.
4. **State Engine**:
   - Implementasikan *finite-state machine (FSM)* sederhana atau reducer deterministik untuk menangani state transitions: `idle`, `suggesting`, `navigating`, `selected`.
   - Menghindari perulangan render yang tidak perlu (*unnecessary re-renders*) saat item yang disorot berubah.

#### Constraints
- **Zero External Dependencies**: Tidak boleh menggunakan library styling maupun headless pihak ketiga apa pun (Floating UI, Radix, Popover API, dll.).
- **Type-Safety Penuh**: Tipe data generik `<T>` harus mengalir mulus dari `items` ke `onSelectedItemChange` dan scoped slot props/item render.
- **Isomorphic Ref Merging**: Semua implementasi DOM forwarding ref harus menggunakan safe ref merger yang mendukung functional refs maupun object refs (`React.MutableRefObject`).

#### Expected Output
1. File modul TypeScript yang memuat:
   - `useCombobox` hook engine.
   - Komponen compound: `Combobox.Root`, `Combobox.Input`, `Combobox.Content`, `Combobox.Item`.
   - Utility pendukung: `mergeRefs`, `composeEventHandlers`.
2. Contoh implementasi konsumen (consumer code) berpagar aksesibilitas tinggi yang me-render list kustom dengan integrasi Tailwind CSS atau CSS biasa via atribut `data-*` (misal: `data-highlighted`, `data-state="open"`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan arsitektural antara *headless state logic*, *accessibility layer*, dan *presentational components*.
- [ ] Anatomi spesifikasi WAI-ARIA 1.2 Authoring Practices Guide (APG) untuk komponen dinamis (Combobox, Dialog, Menu, Tooltip).
- [ ] Mekanisme kerja internal Slot Pattern (`asChild`) dan teknik manipulasi *React Virtual DOM* via `cloneElement` serta `mergeRefs`.
- [ ] Cara kerja finite-state machine (FSM) dalam mengelola siklus hidup komponen UI interaktif dan mencegah *impossible states*.
- [ ] Risiko dan solusi performa layout thrashing (*forced synchronous reflow*) saat memanipulasi fokus dan membaca geometri elemen browser.
- [ ] Perbedaan fundamental arsitektur hook-based (React Aria Hooks) vs component-based primitive (Radix, Ark UI).
- [ ] Mekanisme isolasi event, focus trapping, dan penanganan pointer event pada multi-layer dynamic DOM portals.

### Saya tidak perlu menghafal:
- [ ] Setiap nilai string hexadecimal atau mapping keyboard event code (cukup ketahui abstraksi `event.key` modern seperti `'ArrowDown'`, `'Escape'`).
- [ ] Seluruh formula kalkulasi koordinat geometris floating layer (cukup pahami konsep collision boundary, middleware pipeline, dan relasi *anchor-to-floating coordinates*).
- [ ] Semua konfigurasi internal bundler Rollup/tsup untuk micro-optimasi ukuran tree-shaking headless library.

### Saya harus bisa melakukan:
- [ ] Membangun headless custom hook engine yang mendukung transisi controlled dan uncontrolled state secara deterministik.
- [ ] Menulis utilitas production-grade `mergeRefs` yang aman terhadap mutasi dan lifecycle component unmount.
- [ ] Mengimplementasikan `composeEventHandlers` yang mampu mengevaluasi `event.defaultPrevented` secara berurutan.
- [ ] Mengaudit dan mendebug kebocoran *Accessibility Tree* dan kegagalan screen reader via browser DevTools Accessibility Tree panel.
- [ ] Merancang sistem compound component berbasis Context API yang kebal terhadap *unnecessary re-render cascades* menggunakan fine-grained context selector atau state store terisolasi.
- [ ] Menerapkan atribut semantik `data-*` state (`data-state="open|closed"`, `data-disabled`) sebagai media komunikasi utama antara headless engine dan layer CSS/styling.