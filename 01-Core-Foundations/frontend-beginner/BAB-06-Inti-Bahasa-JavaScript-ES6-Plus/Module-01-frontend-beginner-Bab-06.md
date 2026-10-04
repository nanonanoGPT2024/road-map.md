# Bab 06 Module 01: Arsitektur Event-Driven Browser: Siklus Propagasi DOM Event dan Pola Event Delegation

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
*   Menganalisis siklus hidup event DOM mulai dari *dispatching*, fase *Capturing*, *Target*, hingga fase *Bubbling* sesuai spesifikasi W3C/WHATWG DOM Level 3 Event Model.
*   Mengontrol alur propagasi dan aksi bawaan browser (*default browser behavior*) menggunakan `stopPropagation()`, `stopImmediatePropagation()`, dan `preventDefault()`.
*   Mengidentifikasi perbedaan runtime antara properti `event.target` dan `event.currentTarget` dalam konteks penanganan event hierarkis.
*   Mengimplementasikan pola arsitektur **Event Delegation** dengan efisiensi kompleksitas memori $O(1)$ untuk mereduksi footprint alokasi memori heap pada dynamic elements.
*   Mencegah *detached DOM tree memory leaks* dengan mengimplementasikan lifecycle management event listener menggunakan `AbortController`.

---

### 2. Prerequisite
Sebelum mempelajari materi ini, peserta didik harus memahami:
1.  **Arsitektur DOM Tree**: Hubungan hierarkis Node, Element, Parent, Child, dan Ancestor.
2.  **JavaScript Execution Context**: Single-threaded nature, Call Stack, Task Queue, dan Event Loop.
3.  **DOM Selection API**: Penggunaan `document.querySelector`, `Element.matches`, dan `Element.closest`.
4.  **Primitive Functions & References**: Konsep kesetaraan referensi objek (*by reference vs by value*) pada fungsi JavaScript.

---

### 3. Concept
Browser adalah lingkungan runtime berbasis *event-driven*. Setiap interaksi fisik pengguna (klik mouse, input keyboard, sentuhan layar) dikonversi oleh subsistem sistem operasi menjadi sinyal hardware, diteruskan ke proses *browser engine*, dan akhirnya dipetakan ke dalam antarmuka JavaScript sebagai objek turunan dari interface `EventTarget`.

Siklus hidup DOM Event diatur oleh mekanisme **Event Dispatch and Propagation**:
1.  **Capture Phase (Trickling Phase)**: Event turun dari akar pohon DOM (`Window` -> `Document` -> `<html>` -> `<body>` -> ancestors) menuju parent langsung dari target elemen.
2.  **Target Phase**: Event mencapai elemen terdalam yang memicu interaksi (`event.target`). Pada fase ini, listener dieksekusi secara berurutan sesuai urutan registrasinya.
3.  **Bubble Phase**: Event membalik arah dan merambat naik (*bubble up*) dari elemen target kembali ke elemen `Window`.

```
                        PHASE 1: CAPTURE
                  Window --------------------+
                    |                        |
                 Document                    |
                    |                        |
              <html>, <body>                 |
                    |                        |
             Container <div>                 |
                    |                        v
                    |               PHASE 2: TARGET
                    +----------> <button> (Target)
                                             |
                        PHASE 3: BUBBLE      |
                  Window <-------------------+
                    ^                        
                 Document                    
                    ^                        
              <html>, <body>                 
                    ^                        
             Container <div>                 
```

Interface `EventTarget` menyediakan tiga method fundamental:
*   `addEventListener(type, listener, options)`
*   `removeEventListener(type, listener, options)`
*   `dispatchEvent(event)`

Karakteristik penting dari event ditentukan oleh metadata objeknya:
*   `bubbles` (boolean): Menentukan apakah event akan merambat naik ke ancestor tree pada fase bubbling.
*   `cancelable` (boolean): Menentukan apakah efek default browser dapat dibatalkan via `preventDefault()`.
*   `composed` (boolean): Menentukan apakah event dapat menembus batas Shadow DOM ke Light DOM reguler.

---

### 4. Why
Memahami propagasi event secara mekanistik mutlak diperlukan dalam rekayasa frontend modern karena:

1.  **Konservasi Alokasi Memori Heap**: Mengikat (*binding*) listener individual ke $N$ elemen (misal: 10.000 baris tabel data) menciptakan $N$ closure functions dan internal C++ wrapper objects. Hal ini menyebabkan lonjakan drastis pada V8 Heap Memory dan memicu *Garbage Collection (GC) thrashing*.
2.  **Stabilitas Interaksi Dinamis**: Elemen yang ditambahkan ke DOM secara asinkron (misal: via AJAX/Fetch atau infinite scrolling) tidak memiliki listener terpasang kecuali diikat ulang secara manual, yang rentan terhadap race condition.
3.  **Mitigasi Detached DOM Leaks**: Listener yang tertinggal pada elemen DOM yang telah dihapus (*removed from tree*) dapat mengunci seluruh pohon DOM tersebut di memori heap karena referensi closure yang tertahan.
4.  **Optimasi Metrik Web Vitals**: Pemasangan listener pasif (`{ passive: true }`) krusial untuk mencegah degradasi metrik **Interaction to Next Paint (INP)** dan **Cumulative Layout Shift (CLS)** saat scrolling.

---

### 5. What
Komponen inti dalam ekosistem penanganan event browser:

| Komponen / API | Tipe | Deskripsi Operasional |
| :--- | :--- | :--- |
| `event.target` | `Element` | Elemen terdalam yang secara aktual memicu event (asal interaksi). |
| `event.currentTarget` | `Element` | Elemen yang sedang mengeksekusi callback handler saat propagasi berjalan. |
| `event.stopPropagation()` | `Method` | Menghentikan propagasi event lebih jauh di fase capture maupun bubble. |
| `event.stopImmediatePropagation()`| `Method` | Menghentikan propagasi DAN mencegah handler lain pada elemen yang sama dieksekusi. |
| `event.preventDefault()` | `Method` | Membatalkan aksi default User Agent (misal: submit form, navigasi tautan `<a>`). |
| `options.capture` | `Boolean` | Flag untuk mendaftarkan listener pada Capture Phase jika `true`. Default: `false`. |
| `options.passive` | `Boolean` | Menjamin ke browser bahwa handler tidak akan memanggil `preventDefault()`, membuka optimasi rendering thread. |
| `options.once` | `Boolean` | Listener otomatis dicopot setelah eksekusi pertama. |
| `AbortSignal` | `Object` | Sinyal pembatalan dari `AbortController` untuk mencopot listener secara deklaratif dan batch. |

---

### 6. How
Alur internal browser saat memproses sebuah event klik:

```
[OS Hardware Input Event]
           │
           ▼
[Browser Process] (Menghitung koordinat piksel global)
           │ (IPC Message)
           ▼
[Renderer Process / Compositor Thread]
           │ (Hit-testing: Menentukan node target berdasarkan tree layout)
           ▼
[Main Thread: Event Dispatcher]
           │
           ├─► 1. Bangun Propagation Path: Array node dari Window s.d. Target
           │
           ├─► 2. Execute Capture Phase: Traversal maju dari Index 0 ke N-1
           │      (Eksekusi listener jika { capture: true })
           │
           ├─► 3. Execute Target Phase: Traversal node target
           │      (Eksekusi semua listener pada target)
           │
           ├─► 4. Execute Bubble Phase: Traversal mundur dari Index N-1 ke 0
           │      (Eksekusi listener jika { capture: false })
           │
           └─► 5. Default Action Execution: Jika `defaultPrevented === false`
```

---

### 7. Analogy
Bayangkan sebuah **Gedung Perkantoran Multinasional**:
*   **Window/Document**: Pos Keamanan Gerbang Utama Gedung.
*   **Container**: Resepsionis Lantai.
*   **Target (`<button>`)**: Karyawan di kubikel spesifik.

1.  **Capture Phase**: Paket dikirim dari Luar Gedung. Kurir masuk melalui Gerbang Utama (Window), melewati Resepsionis Lantai (Container), hingga mencapai Kubikel Karyawan (Target).
2.  **Target Phase**: Paket diserahkan dan dibuka oleh Karyawan tersebut.
3.  **Bubble Phase**: Tanda terima paket dibawa kembali keluar: dari Kubikel Karyawan, naik melintasi Resepsionis Lantai, hingga diverifikasi ulang di Gerbang Utama.

*   `target`: Karyawan yang memesan paket.
*   `currentTarget`: Pos pemeriksaan mana pun yang sedang memegang paket tersebut saat itu.
*   `stopPropagation()`: Resepsionis memutuskan tanda terima tidak boleh dibawa keluar gedung, menghentikan laporan ke Pos Keamanan.
*   `preventDefault()`: Pembatalan instruksi internal paket (misal: membatalkan instruksi langsung merakit barang).

---

### 8. Diagram
Diagram alur propagasi detail melalui pohon hierarki DOM:

```
                  ========================================
                               WINDOW LEVEL
                  ========================================
                   |                                    ^
        [1] CAPTURE|                                    | [7] BUBBLE
                   v                                    |
                  ========================================
                              DOCUMENT LEVEL
                  ========================================
                   |                                    ^
        [2] CAPTURE|                                    | [6] BUBBLE
                   v                                    |
                  ========================================
                            <div id="container">
                  ========================================
                   |                                    ^
        [3] CAPTURE|                                    | [5] BUBBLE
                   v                                    |
                  ========================================
                        <button id="btn-action">
                             TARGET PHASE [4]
                  ========================================
```

Perbedaan Referensi Properti Event:
```
Saat event berada di <div id="container">:
┌────────────────────────────────────────────────────────┐
│ event.target        ───► <button id="btn-action">      │ (Pemicu awal)
│ event.currentTarget ───► <div id="container">          │ (Pemegang listener)
└────────────────────────────────────────────────────────┘
```

---

### 9. Simple Example
Kode demonstrasi alur eksekusi fase Capturing dan Bubbling:

```html
<!DOCTYPE html>
<html lang="en">
<body>
  <div id="parent" style="padding: 20px; background: #eee;">
    Parent Element
    <button id="child">Child Element</button>
  </div>

  <script>
    const parent = document.getElementById('parent');
    const child = document.getElementById('child');

    // 1. Capture Listener pada Parent
    parent.addEventListener('click', (e) => {
      console.log('1. Parent (Capture Phase)');
    }, { capture: true });

    // 2. Bubble Listener pada Parent
    parent.addEventListener('click', (e) => {
      console.log('4. Parent (Bubble Phase)');
    }, { capture: false });

    // 3. Target Listeners pada Child
    child.addEventListener('click', (e) => {
      console.log('2. Child (Target Execution - A)');
    });

    child.addEventListener('click', (e) => {
      console.log('3. Child (Target Execution - B)');
    });

    // OUTPUT KETIKA TOMBOL DI-KLIK:
    // 1. Parent (Capture Phase)
    // 2. Child (Target Execution - A)
    // 3. Child (Target Execution - B)
    // 4. Parent (Bubble Phase)
  </script>
</body>
</html>
```

---

### 10. Practical Example
Implementasi sistem **Dynamic Data Table** interaktif berbasis **Event Delegation**, lengkap dengan manajemen alokasi memori menggunakan `AbortController` dan `dataset`.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Data Table Event Delegation</title>
  <style>
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
    .badge-active { background-color: #d4edda; color: #155724; padding: 2px 6px; }
    .badge-inactive { background-color: #f8d7da; color: #721c24; padding: 2px 6px; }
  </style>
</head>
<body>

  <button id="btn-add-row">Add Transaction Row Dynamically</button>
  <button id="btn-destroy">Destroy Table Listeners (Teardown)</button>

  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Description</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="transaction-tbody">
      <tr data-row-id="tx-101">
        <td>101</td>
        <td>Server Subscription Renewal</td>
        <td><span class="badge-active">Success</span></td>
        <td>
          <button data-action="view" class="action-btn">View Details</button>
          <button data-action="delete" class="action-btn">Delete</button>
        </td>
      </tr>
    </tbody>
  </table>

  <script>
    class TransactionTableController {
      /** @type {HTMLTableSectionElement} */
      #tbody;
      /** @type {AbortController} */
      #abortController;

      constructor(tbodySelector) {
        this.#tbody = document.querySelector(tbodySelector);
        this.#abortController = new AbortController();
        this.#init();
      }

      #init() {
        const { signal } = this.#abortController;

        // SINGLE EVENT LISTENER untuk seluruh baris yang ada saat ini & masa depan
        this.#tbody.addEventListener('click', this.#handleTableClick.bind(this), { signal });
      }

      /**
       * @param {MouseEvent} event 
       */
      #handleTableClick(event) {
        // Guard Clause: Pastikan event.target adalah Element node
        if (!(event.target instanceof Element)) return;

        // Cari elemen interaktif terdekat yang memiliki data-action
        const actionButton = event.target.closest('button[data-action]');
        
        // Klik terjadi di luar tombol aksi dalam tabel
        if (!actionButton || !this.#tbody.contains(actionButton)) {
          return;
        }

        // Ambil baris parent menggunakan closest
        const row = actionButton.closest('tr[data-row-id]');
        if (!row) return;

        const rowId = row.getAttribute('data-row-id');
        const actionType = actionButton.dataset.action;

        this.#dispatchAction(actionType, rowId, row);
      }

      #dispatchAction(action, rowId, rowElement) {
        switch (action) {
          case 'view':
            console.info(`[ACTION VIEW]: Fetching details for Record ${rowId}`);
            break;
          case 'delete':
            console.warn(`[ACTION DELETE]: Removing row ${rowId}`);
            rowElement.remove();
            break;
          default:
            console.error(`Unhandled action type: ${action}`);
        }
      }

      addRow(id, description, status) {
        const tr = document.createElement('tr');
        tr.setAttribute('data-row-id', id);
        tr.innerHTML = `
          <td>${id}</td>
          <td>${description}</td>
          <td><span class="${status === 'Success' ? 'badge-active' : 'badge-inactive'}">${status}</span></td>
          <td>
            <button data-action="view" class="action-btn">View Details</button>
            <button data-action="delete" class="action-btn">Delete</button>
          </td>
        `;
        this.#tbody.appendChild(tr);
      }

      destroy() {
        // Mencopot listener secara atomik tanpa kebocoran memori
        this.#abortController.abort();
        console.log('[LIFECYCLE]: TransactionTableController listeners successfully detached.');
      }
    }

    // Inisialisasi
    const tableController = new TransactionTableController('#transaction-tbody');

    // Demonstrasi penambahan baris secara dinamis
    let counter = 102;
    document.getElementById('btn-add-row').addEventListener('click', () => {
      tableController.addRow(
        `tx-${counter}`, 
        `Dynamic Transaction #${counter}`, 
        counter % 2 === 0 ? 'Success' : 'Failed'
      );
      counter++;
    });

    // Teardown trigger
    document.getElementById('btn-destroy').addEventListener('click', () => {
      tableController.destroy();
    });
  </script>
</body>
</html>
```

---

### 11. Real World Example
#### Kasus: E-Commerce Product Catalog Feed (Contoh: Pola Arsitektur Tokopedia / Amazon)

**Masalah Arsitektural**:
Katalog e-commerce memuat ratusan produk via *infinite scroll*. Setiap produk memiliki elemen interaktif: tombol *Wishlist*, tombol *Add to Cart*, pemilih varian warna, dan tautan gambar. 

Jika developer mengikat event listener langsung pada setiap komponen kartu produk:
*   1.000 produk $\times$ 4 listener/produk = 4.000 listener aktif di memory heap.
*   Saat produk dihapus dari DOM akibat virtualisasi list, developer sering lupa mengeksekusi `removeEventListener`. Objek C++ DOM wrapper tertinggal di V8 Heap (**Detached HTMLElement Leak**).
*   Browser mengalami frame drop (menurun di bawah 60 FPS) akibat alokasi memori masif dan siklus GC yang sering terpicu.

**Solusi Skala Industri**:
Platform menerapkan arsitektur *Single Root Delegator* pada elemen `<main id="catalog-feed">`.

```javascript
// Infrastruktur Delegasi Katalog Skala Industri
class ProductCatalogEngine {
  constructor(rootContainer) {
    this.root = rootContainer;
    this.controller = new AbortController();
    this.setupDelegator();
  }

  setupDelegator() {
    this.root.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      // 1. Delegasi Action: Add to Cart
      const cartBtn = target.closest('[data-analytics-id="btn-add-to-cart"]');
      if (cartBtn && this.root.contains(cartBtn)) {
        event.preventDefault();
        const productId = cartBtn.dataset.productId;
        this.handleAddToCart(productId);
        return;
      }

      // 2. Delegasi Action: Toggle Wishlist
      const wishlistBtn = target.closest('[data-analytics-id="btn-wishlist"]');
      if (wishlistBtn && this.root.contains(wishlistBtn)) {
        event.preventDefault();
        const productId = wishlistBtn.dataset.productId;
        this.handleToggleWishlist(productId, wishlistBtn);
        return;
      }
    }, { 
      signal: this.controller.signal,
      capture: false,
      passive: false 
    });
  }

  handleAddToCart(id) {
    // Pipeline integrasi ke State Manager / API
    console.log(`Dispatched Global Cart Event for Product: ${id}`);
  }

  handleToggleWishlist(id, element) {
    element.classList.toggle('active');
    console.log(`Toggled Wishlist State for Product: ${id}`);
  }

  teardown() {
    this.controller.abort();
  }
}
```

---

### 12. Trade-offs

```
              Direct Binding vs Event Delegation
  ┌───────────────────────────────────────────────────────┐
  │ DIRECT BINDING                                        │
  │ Memori: O(N) [Rentan Leaks]                           │
  │ CPU saat Event: O(1) [Langsung ke target]             │
  │ Dinamisme DOM: Rendah [Perlu bind ulang manual]       │
  ├───────────────────────────────────────────────────────┤
  │ EVENT DELEGATION                                      │
  │ Memori: O(1) [Sangat Ringan]                          │
  │ CPU saat Event: O(D) [D = Kedalaman DOM via closest()]│
  │ Dinamisme DOM: Tinggi [Elemen baru langsung aktif]    │
  └───────────────────────────────────────────────────────┘
```

| Parameter Evaluasi | Direct Event Binding | Event Delegation Pattern |
| :--- | :--- | :--- |
| **Complexity (Arsitektural)** | Rendah. Pemasangan deklaratif per node. | Menengah. Memerlukan parsing selektor via `.closest()`. |
| **Memory Consumption** | $O(N)$ proporsional terhadap total elemen. | $O(1)$ hanya 1 listener pada ancestor. |
| **Runtime Performance** | Eksekusi instan saat event terjadi. | Sedikit overhead parsing DOM traversal (`closest`). |
| **Lifecycle Cleanliness** | Rentan Memory Leaks jika node dihapus tanpa unbound. | Sangat aman; node dapat dihapus bebas tanpa leak listener. |
| **Focus/Blur Handling** | Natural; langsung didukung semua event. | Rumit; event seperti `focus`/`blur` tidak melakukan bubble. |

---

### 13. When To Use
*   Ketika menangani list dinamis di mana item dapat ditambah, diurutkan, atau dihapus secara real-time via data stream atau manipulasi DOM.
*   Ketika render antarmuka memiliki jumlah elemen identik yang tinggi (misal: spreadsheet grid, papan kanban, data tables, product grids).
*   Untuk menyatukan logging telemetri atau analytics tracker global (menangkap semua klik link/tombol yang memiliki atribut `data-analytics-*`).

---

### 14. When NOT To Use
*   **Event yang tidak melakukan bubbling**: Event seperti `focus`, `blur`, `mouseenter`, `mouseleave`, `load`, `unload`. Solusi jika tetap ingin delegasi: gunakan alternatif yang melakukan bubble (`focusin`, `focusout`) atau manfaatkan **Capture Phase** (`{ capture: true }`).
*   **Struktur Pohon DOM Sangat Dalam dengan Beban Interaksi Ekstrem**: Jika traversal `Element.closest()` harus menelusuri puluhan tingkat parent node dalam frekuensi event yang sangat rapat (misal: event `mousemove` berkepanjangan), pemanggilan traversal DOM berulang dapat menurunkan throughput frame rendering.
*   **Komponen Terisolasi Tingkat Tinggi (Single Micro-Widgets)**: Widget tunggal mandiri tanpa elemen anak dinamis (misal: tombol audio play tunggal).

---

### 15. Common Mistakes
1.  **Menggunakan Anonymous Function pada Listener Tanpa Manajemen Siklus Hidup**:
    ```javascript
    // BAD: Listener ini tidak pernah bisa di-remove manual!
    window.addEventListener('resize', () => { /* Logic */ });
    ```
2.  **Menyamakan `e.target` dengan `e.currentTarget` pada Event Delegation**:
    ```javascript
    // BAD: Jika tombol memiliki icon SVG di dalamnya,
    // e.target bisa mengarah ke SVGPathElement, BUKAN <button>!
    parent.addEventListener('click', (e) => {
      const id = e.target.getAttribute('data-id'); // BISA NULL!
    });

    // GOOD: Gunakan closest()
    parent.addEventListener('click', (e) => {
      const btn = e.target.closest('button');
      if (btn) {
        const id = btn.getAttribute('data-id');
      }
    });
    ```
3.  **Menyalahgunakan `stopPropagation()` Tanpa Alasan Jelas**:
    Memanggil `e.stopPropagation()` secara serampangan akan merusak library eksternal, web metrics (Google Tag Manager), atau modul analitik yang memantau interaksi dari level `document`.
4.  **Lupa Menentukan Flag `{ passive: true }` pada Event Touch/Scroll**:
    Menyebabkan browser menunda composite scrolling pada UI thread karena menunggu eksekusi JS thread selesai untuk memastikan ada/tidaknya `e.preventDefault()`.

---

### 16. Best Practices (Production Checklist)
*   [ ] Gunakan `event.target.closest(selector)` untuk memvalidasi elemen delegasi, bukan `event.target.matches()` atau checking tag manual.
*   [ ] Pastikan mengecek containment: `parentContainer.contains(matchedElement)` agar selector tidak mencocokkan elemen di luar batas container terkait.
*   [ ] Pasang `{ passive: true }` secara eksplisit pada event berfrekuensi tinggi seperti `touchstart`, `touchmove`, `wheel`.
*   [ ] Gunakan `AbortController` API untuk mempermudah pelepasan massal (*bulk deregistration*) event listener saat modul di-unmount.
*   [ ] Berikan penamaan deskriptif pada method handler (contoh: `#handleOrderListClick`) daripada menggunakan inline fat-arrow function anonim.
*   [ ] Gunakan atribut `data-*` semantik (misal: `data-action="approve"`) sebagai *contract interface* pemetaan handler, bukan mengandalkan CSS class name yang rentan refactoring style.

---

### 17. Troubleshooting
#### Masalah 1: Detached DOM Node Memory Leak
*   *Gejala*: Aplikasi single-page application (SPA) terasa semakin lambat seiring navigasi; memory usage di Chrome Task Manager terus meningkat.
*   *Diagnosis*:
    1. Buka Chrome DevTools -> **Memory Tab**.
    2. Ambil **Heap Snapshot**.
    3. Filter pencarian dengan kata kunci `Detached`.
    4. Cari elemen yang memiliki referensi tersisa ke `EventListener`.
*   *Solusi*: Terapkan arsitektur teardown berbasis `AbortController.abort()` saat komponen dilepas dari DOM.

#### Masalah 2: Event Delegation Mengalami False-Positive Target pada Elemen Bersarang (*Nested Elements*)
*   *Gejala*: Klik pada ikon/label di dalam tombol menghasilkan `e.target` berupa `<i>` atau `<span>`, sehingga pembacaan atribut tombol gagal.
*   *Solusi*:
    ```javascript
    // Pastikan traversal menjangkau anchor container terdekat:
    const actionElement = e.target.closest('[data-action]');
    if (!actionElement || !container.contains(actionElement)) return;
    ```

---

### 18. Exercise
**Instruksi Pengerjaan**:
1. Buat dokumen HTML yang menampilkan elemen list `<ul>` dengan ID `#task-list`.
2. Sediakan satu tombol statis di luar list: `#btn-add-task`.
3. Buat implementasi JavaScript tanpa library dengan ketentuan:
   * Menggunakan pola **Event Delegation** (hanya boleh ada SATU event listener untuk seluruh item list).
   * Setiap item list yang dibuat dinamis memiliki struktur:
     ```html
     <li data-task-id="UUID">
       <span class="task-title">Nama Task</span>
       <button data-action="toggle">Done</button>
       <button data-action="delete">Delete</button>
     </li>
     ```
   * Tombol `#btn-add-task` akan memasukkan item baru ke `#task-list`.
   * Klik tombol `Done` mencoret teks tugas (`text-decoration: line-through`).
   * Klik tombol `Delete` menghapus elemen `<li>` terkait secara instan dari DOM.

---

### 19. Challenge
Rancang sebuah class arsitektural bernama `GlobalActionBus`:
1. Class ini harus mengikat **hanya 1 event listener global** pada `document.documentElement` untuk tipe event `click`.
2. Sediakan method API: `registerAction(actionName, handlerCallback)`.
3. Komponen DOM di mana pun cukup menulis markup HTML seperti:
   ```html
   <button data-dispatch="user:delete" data-payload='{"id": 42}'>Delete User</button>
   ```
4. Saat tombol diklik:
   * `GlobalActionBus` mengekstrak atribut `data-dispatch`.
   * Membaca dan mem-parsing JSON yang tersimpan pada `data-payload`.
   * Mengeksekusi handlerCallback yang terdaftar untuk aksi tersebut dengan passing parameter data payload dan instans elemen target.
5. Tangani skenario edge case: validasi kesalahan JSON parse secara aman (tidak boleh melempar unhandled error yang memutus rantai eksekusi event).
6. Terapkan flag lifecycle `unregisterAction(actionName)`.

---

### 20. Summary
*   Model Event DOM beroperasi dalam tiga fase terstruktur: **Capturing Phase**, **Target Phase**, dan **Bubbling Phase**.
*   `event.target` merujuk ke elemen awal pemicu interaksi, sedangkan `event.currentTarget` merujuk ke elemen yang callback listener-nya sedang dieksekusi.
*   Pola **Event Delegation** mengeksploitasi fase *Bubbling* untuk menangani ribuan event elemen turunan (termasuk elemen dinamis masa depan) dengan hanya memasang satu listener pada elemen ancestor, mengoptimalkan memori heap ke $O(1)$.
*   Pencegahan alur propagasi dan default behavior wajib dilakukan secara presisi menggunakan `stopPropagation()` dan `preventDefault()`.
*   Eksekusi modern skala produksi mewajibkan decoupling dan pembersihan memory leak menggunakan `AbortController` serta pemanfaatan flag performa `{ passive: true }`.