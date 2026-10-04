# Bab 05 Module 01: Arsitektur Document Object Model (DOM), Traversal Tingkat Lanjut, dan Manipulasi Node Berperforma Tinggi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik memiliki kemampuan terukur untuk:
*   Menganalisis siklus hidup representasi C++ DOM tree pada browser engine (*Blink/Gecko/WebKit*) dan jembatannya dengan JavaScript runtime engine (*V8/SpiderMonkey*).
*   Melakukan traversal hierarki DOM menggunakan API standar modern secara deterministik tanpa terdistorsi oleh *text/whitespace nodes*.
*   Merancang manipulasi node performa tinggi dengan menerapkan teknik *batched mutations* via `DocumentFragment` dan antrean `requestAnimationFrame` untuk mencegah *Forced Synchronous Layout* (*Layout Thrashing*).
*   Mengidentifikasi dan mengeliminasi *detached DOM tree memory leaks* menggunakan Chrome DevTools Heap Snapshot.
*   Mengimplementasikan mutasi antarmuka berbasis DOM murni yang lolos uji batas anggaran render 60 FPS (frame budget $<16.67\text{ ms}$).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
*   **Struktur Pohon HTML5**: Pemahaman parsing semantik dokumen dan hierarki elemen.
*   **CSSOM & Pipeline Render Browser**: Konsep dasar *Critical Rendering Path* (Parse HTML $\to$ DOM, Parse CSS $\to$ CSSOM, Render Tree, Layout, Paint, Composite).
*   **JavaScript Core ES6+**: *Scope*, *Closures*, referensi objek, *garbage collection* (mark-and-sweep), dan dasar asinkronus (Promise & Task Queue).

---

### 3. Concept
Document Object Model (DOM) bukanlah bagian dari spesifikasi bahasa pemrograman ECMAScript (JavaScript), melainkan sebuah Application Programming Interface (API) lintas platform berbasis representasi pohon objek berbasis spesifikasi W3C/WHATWG yang disediakan oleh lingkungan runtime browser (*host environment*). 

Secara arsitektural:
*   **Engine Boundary Bridge**: Di dalam browser engine (misalnya Chromium dengan Blink dan V8), DOM diimplementasikan menggunakan C++. Ketika JavaScript mengakses objek seperti `document.getElementById`, eksekusi harus menyeberangi jembatan bahasa (*Web IDL bindings*). Penyeberangan konteks (*context boundary crossing*) ini membawa latensi komputasi kecil, tetapi akumulasinya signifikan jika dipanggil di dalam loop masif.
*   **Pohon Hirarki Node vs Element**: Seluruh elemen di dalam DOM merupakan turunan dari antarmuka dasar `Node`. Spesialisasi objek diturunkan melalui pola prototipikal:
    $$\text{EventTarget} \leftarrow \text{Node} \leftarrow \text{Element} \leftarrow \text{HTMLElement} \leftarrow \text{HTMLDivElement}$$
    Perbedaan fundamental: `Node` mencakup komentar (*Comment*), teks dokumen (*Text Node*, termasuk enter/spasi), dan dokumen itu sendiri (*Document*). Sedangkan `Element` secara eksklusif hanya merepresentasikan tag HTML.
*   **DOM Tree vs Render Tree**: DOM tree memuat seluruh elemen struktural dan teks. Render tree hanya memuat node yang secara visual berpartisipasi dalam rendering (elemen dengan `display: none` atau node `<head>` dieksklusikan dari Render Tree, sedangkan `visibility: hidden` tetap masuk karena memakan ruang layout).
*   **Layout Invalidation Flag**: Setiap kali node DOM diubah posisinya, ukurannya, atau strukturnya, browser menandai sub-pohon (*subtree*) terkait dengan status *dirty layout bit*. Evaluasi ulang geometri (*Reflow/Layout*) ditangguhkan oleh browser hingga akhir mikro-task, kecuali jika ada kode JavaScript yang memaksa pembacaan metrik visual seketika.

---

### 4. Why
Memahami arsitektur DOM tingkat rendah adalah pembeda mutlak antara *script-kiddie* dan *Software Engineer*:
1.  **Pencegahan Layout Thrashing (Jank Elimination)**: Salah satu penyebab utama aplikasi web terasa lambat atau patah-patah (*jank*) adalah pembacaan (*reading*) metrik layout tepat setelah penulisan (*writing*) ke DOM berulang kali. Ini memaksa browser menghentikan thread JS untuk menghitung ulang layout geometris seketika (*Forced Synchronous Layout*).
2.  **Efisiensi Memori (Zero Detached Nodes)**: Node DOM yang dilepas dari dokumen via JavaScript tetapi referensinya masih tersimpan di dalam variabel global atau *closure* tidak akan dibersihkan oleh Garbage Collector. Hal ini menyebabkan kebocoran memori (*Memory Leak*) yang membuat tab browser membengkak seiring waktu.
3.  **Fondasi Virtual DOM / Framework Interaktif**: Framework modern (React, Vue, Svelte) pada dasarnya hanyalah sistem abstraksi berbasis kompilasi dan komputasi runtime untuk meminimalisasi operasi imperatif DOM C++ binding ini. Memahami DOM murni memungkinkan arsitek frontend mendiagnosis masalah performa yang tidak terlihat di tingkat framework.

---

### 5. What
Komponen inti pada sistem DOM mencakup:

*   **Node Identity Types**:
    *   `Node.ELEMENT_NODE` (nilai: 1): Tag HTML terdefinisi.
    *   `Node.TEXT_NODE` (nilai: 3): Konten teks literal, termasuk newline.
    *   `Node.COMMENT_NODE` (nilai: 8): Komentar HTML.
    *   `Node.DOCUMENT_FRAGMENT_NODE` (nilai: 11): Penampung node virtual ringan tanpa parent.
*   **Traversal Vectors**:
    *   *Node-based traversal* (inklusif teks & komentar): `parentNode`, `childNodes`, `firstChild`, `nextSibling`.
    *   *Element-based traversal* (hanya elemen tag): `parentElement`, `children`, `firstElementChild`, `nextElementSibling`.
*   **Mutation Protocols**:
    *   *Legacy/Heavy*: `appendChild()`, `removeChild()`, `innerHTML` (memicu parser HTML ulang menyeluruh).
    *   *Modern/High-Performance*: `append()`, `prepend()`, `replaceChildren()`, `insertAdjacentHTML()`, `DocumentFragment`.
*   **Observer Interfaces**:
    *   `MutationObserver`: API bawaan browser untuk memonitor perubahan struktur DOM secara asinkron tanpa memblokir thread rendering utama.

---

### 6. How
Alur kerja mutasi dan sinkronisasi DOM mengikuti protokol berikut:

```
[ JavaScript Mutation Call ]
           │
           ▼
[ V8 to Blink C++ Binding ]
           │
           ▼
[ DOM In-Memory Mutation ] ──> (Mark Subtree 'Dirty')
           │
     ┌─────┴────────────────────────────────┐
     ▼                                      ▼
[ Batching via Fragment / Loop ]    [ Immediate Metric Read? ]
     │                              (e.g., offsetTop, clientWidth)
     │                                      │
     │                                      ├─── YES ──> [ FORCED SYNCHRONOUS LAYOUT ]
     │                                      │            (Reflow blocking JS thread)
     │                                      └─── NO
     │                                           │
     ▼                                           ▼
[ Frame Pipeline Schedule ] <────────────────────┘
           │
           ▼
[ Recalculate Styles ]
           │
           ▼
[ Layout Calculation (Reflow) ]
           │
           ▼
[ Paint (Rasterization) ]
           │
           ▼
[ Composite Layers to GPU ]
```

1.  **Fase Parse & Binding**: JavaScript mengeksekusi instruksi modifikasi via Web IDL.
2.  **Dirty Flagging**: Elemen yang dimutasi ditandai kotor (*dirty bit*).
3.  **Microtask Deferred Execution**: Browser menunda perhitungan ulang layout visual hingga antrean kode JavaScript selesai diproses (*call stack empty*).
4.  **Render Lifecycle Execution**: Pada awal siklus *vsync* display hardware (biasanya interval 16.6ms pada monitor 60Hz), browser mengevaluasi Recalculate Style, Layout, Paint, dan Composite secara berurutan.

---

### 7. Analogy
Bayangkan DOM seperti **papan susun huruf cetak mekanik** di sebuah percetakan koran kuno:
*   **JavaScript** adalah operator editor naskah.
*   **Pohon DOM** adalah susunan balok-balok huruf timbal yang diletakkan pada cetakan dasar.
*   **Layar Browser** adalah lembaran kertas koran yang dicetak.

Jika editor ingin mengganti 100 kata dalam paragraf:
*   *Pola Buruk (Direct Single Mutation)*: Setiap kali mengganti satu balok huruf, editor menyuruh mesin cetak menekan tinta ke kertas untuk melihat hasilnya (Layout + Paint seketika). Mengganti 100 balok berarti 100 kali proses cetak manual. Mesin aus, waktu terbuang, proses lambat drastis (*Layout Thrashing*).
*   *Pola Benar (`DocumentFragment`)*: Editor mengambil sebuah baki kayu terpisah (*off-screen buffer*), menyusun 100 balok huruf tersebut secara rapi di atas baki, lalu dalam satu gerakan tunggal memindahkan seluruh balok baru itu ke cetakan utama mesin percetakan. Mesin cetak hanya berjalan **satu kali** setelah seluruh susunan selesai.

---

### 8. Diagram
Arsitektur runtime batas jembatan JavaScript vs Browser Engine:

```
+-------------------------------------------------------------------------+
| BROWSER PROCESS / RENDERER THREAD                                       |
|                                                                         |
|  +-------------------------+             +---------------------------+  |
|  |   JavaScript Engine     |             |    Rendering Engine       |  |
|  |        (e.g. V8)        |             |      (e.g. Blink)         |  |
|  |                         |             |                           |  |
|  |  +-------------------+  |   Web IDL   |  +---------------------+  |  |
|  |  | JS Execution      |  |  Bindings   |  | C++ DOM Tree Nodes  |  |  |
|  |  | Context           |  |<===========>|  | (Live in C++ Heap)  |  |  |
|  |  +-------------------+  |   Crossing  |  +---------------------+  |  |
|  |                         |  Overhead   |             |             |  |
|  |  +-------------------+  |             |             v             |  |
|  |  | GC Heap           |  |             |  +---------------------+  |  |
|  |  | (Wrappers & Refs) |  |             |  | Render Tree Engine  |  |  |
|  |  +-------------------+  |             |  +---------------------+  |  |
|  +-------------------------+             +-------------|-------------+  |
|                                                        |                |
|                                                        v                |
|                                            +---------------------+      |
|                                            | Layout & Paint      |      |
|                                            | (Hardware Draw)     |      |
|                                            +---------------------+      |
+-------------------------------------------------------------------------+
```

---

### 9. Simple Example
Contoh dasar perbedaan traversal `childNodes` (Node) vs `children` (Element) serta penggunaan mutasi modern:

```html
<!-- index.html -->
<ul id="parent-list">
  <!-- Ini adalah komentar -->
  <li>Item Indeks 0</li>
  <li>Item Indeks 1</li>
</ul>
```

```javascript
// main.js
const list = document.getElementById('parent-list');

// 1. Perbedaan Node vs Element Traversal
console.log(list.childNodes.length); 
// Output: 5 (Text "\n  ", Comment, Text "\n  ", Element <li>, Text "\n  ", Element <li>, Text "\n")

console.log(list.children.length); 
// Output: 2 (Hanya menghitung <li> sebagai HTML Element)

// 2. Traversal deterministik (Element Only)
const firstLi = list.firstElementChild;
const secondLi = firstLi.nextElementSibling;
console.log(secondLi.textContent); // "Item Indeks 1"

// 3. Mutasi Modern Deklaratif Tanpa Layout Recalculation Berlebih
const newLi = document.createElement('li');
newLi.textContent = 'Item Indeks 2';
list.append(newLi); // Modern API: menerima Node atau DOMString, mendukung multiple arguments
```

---

### 10. Practical Example
Berikut adalah implementasi sistem pembaruan tabel data transaksi skala besar yang mengeliminasi masalah *Layout Thrashing* menggunakan batching `DocumentFragment` dan siklus render `requestAnimationFrame`:

```javascript
/**
 * Data Transaction Renderer Berperforma Tinggi
 * Menangani rendering ratusan transaksi tanpa memicu jank pada UI thread.
 */

// Model data tiruan
const generateTransactions = (count) => {
  return Array.from({ length: count }, (_, i) => ({
    id: `TXN-${1000 + i}`,
    timestamp: new Date(Date.now() - i * 60000).toISOString(),
    amount: (Math.random() * 500).toFixed(2),
    status: i % 3 === 0 ? 'COMPLETED' : 'PENDING'
  }));
};

class TransactionTableRenderer {
  /**
   * @param {HTMLElement} tableBodyElement 
   */
  constructor(tableBodyElement) {
    if (!(tableBodyElement instanceof HTMLTableSectionElement)) {
      throw new TypeError("Container harus berupa elemen <tbody> yang valid.");
    }
    this.tBody = tableBodyElement;
  }

  /**
   * Render batch transaksi menggunakan DocumentFragment
   * @param {Array<Object>} transactions 
   */
  renderOptimized(transactions) {
    // 1. Buat DocumentFragment sebagai container off-screen
    const fragment = document.createDocumentFragment();

    // 2. Loop murni di memori (V8 Engine saja, tanpa menyentuh Layout Tree)
    for (let i = 0; i < transactions.length; i++) {
      const txn = transactions[i];
      const row = document.createElement('tr');
      row.setAttribute('data-id', txn.id);

      // Gunakan innerHTML pada detached element relatif aman dan cepat untuk batch
      row.innerHTML = `
        <td>${txn.id}</td>
        <td>${txn.timestamp}</td>
        <td>$${txn.amount}</td>
        <td><span class="badge ${txn.status.toLowerCase()}">${txn.status}</span></td>
      `;

      fragment.appendChild(row);
    }

    // 3. Batch write disinkronkan ke frame berikutnya melalui rAF
    window.requestAnimationFrame(() => {
      // Mengosongkan kontainer lama dan menyuntikkan subtree baru secara atomik
      this.tBody.replaceChildren(fragment);
    });
  }

  /**
   * Peringatan: Anti-pattern! Contoh kode buruk yang memicu Forced Reflow
   * Jangan gunakan di produksi.
   */
  renderAntiPattern(transactions) {
    // KESALAHAN: Membaca layout seketika setelah mutasi di dalam loop
    transactions.forEach(txn => {
      const row = document.createElement('tr');
      row.innerHTML = `<td>${txn.id}</td><td>$${txn.amount}</td>`;
      this.tBody.appendChild(row); // WRITE: Invalidasi layout

      // READ: Memaksa browser menghitung reflow seketika di setiap iterasi!
      const currentHeight = this.tBody.offsetHeight; 
      console.log(`Current Height: ${currentHeight}px`);
    });
  }
}

// Penggunaan di DOM:
// const tBody = document.querySelector('#tx-table tbody');
// const renderer = new TransactionTableRenderer(tBody);
// renderer.renderOptimized(generateTransactions(500));
```

---

### 11. Real World Example
**Kasus Arsitektur: Infinite Scroll Feed Perusahaan E-Commerce Global**

Pada aplikasi berskala besar seperti dashboard inventaris enterprise atau platform e-commerce dengan sistem infinite scroll (misal: Tokopedia, Shopee, Amazon), rendering 5000+ kartu produk secara langsung mengakibatkan memory consumption melonjak hingga ratusan megabyte dan frame drop signifikan ($<15 \text{ FPS}$).

**Implementasi Solusi**:
1.  **DOM Recycling via Virtual Scrolling**: Alih-alih me-render seluruh 5.000 elemen, arsitek merekayasa DOM pool yang hanya mempertahankan 20-30 node aktif yang masuk dalam *viewport* pengguna ditambah buffer atas/bawah.
2.  **Separasi Read/Write Engine**: Penggunaan pustaka mikro internal berbasis pola *FastDOM*. Seluruh operasi pembacaan metrik geometri DOM (`getBoundingClientRect()`, `scrollTop`) dijadwalkan pada antrean pembacaan (`measure`), sementara mutasi struktural (`classList`, `appendChild`, `transform`) diantrekan secara terisolasi pada fase penulisan (`mutate`).
3.  **Hasil**: Penurunan pemakaian RAM dari $480\text{ MB}$ menjadi stabil pada $45\text{ MB}$, dan latensi gulir (*scroll latency*) tetap terjaga stabil di $60\text{ FPS}$ ($16.6\text{ ms per frame}$).

---

### 12. Trade-offs

| Aspek | Direct / Raw DOM Manipulation | Batched DOM (`DocumentFragment` / Virtual Sync) |
| :--- | :--- | :--- |
| **Advantages** | Eksekusi instan untuk target tunggal tanpa alokasi memori tambahan; kode minimalis. | Menghilangkan *layout thrashing*, menekan jumlah reflow/paint ke angka 1 per siklus frame. |
| **Disadvantages** | Rentan memicu reflow berganda secara liar (*cumulative layout delay*). | Memerlukan manajemen alokasi objek sementara di heap memory. |
| **Complexity** | Sangat rendah ($\mathcal{O}(1)$ secara konseptual kode). | Menengah: Membutuhkan pemisahan mutasi antara *read* dan *write phase*. |
| **Performance** | Terdegradasi drastis saat menangani volume elemen $>100$ node secara berulang. | Sangat optimal ($\mathcal{O}(N)$ node dimutasi dengan biaya render fixed $\mathcal{O}(1)$ frame draw). |
| **Cost** | Murah di awal, sangat mahal dalam hal debugging performa ketika aplikasi membesar. | Biaya arsitektural di awal untuk standardisasi fungsi utilitas rendering DOM. |

---

### 13. When To Use
*   Ketika membangun komponen antarmuka mandiri tanpa *framework* (*vanilla micro-frontends*).
*   Pada optimasi modul berkecepatan kritis seperti kanvas *drag-and-drop*, *virtual list/table*, atau visualisasi *dashboard* waktu-nyata (*real-time WebSocket updates*).
*   Ketika mengisolasi *DOM manipulation* di dalam Web Components (*Custom Elements* & *Shadow DOM*).
*   Saat mendesain pustaka (*library/SDK*) pihak ketiga yang harus memiliki ukuran paket (*bundle size*) sangat kecil tanpa dependensi framework eksternal.

---

### 14. When NOT To Use
*   Aplikasi form bisnis skala besar dengan ratusan validasi status silang (*cross-field state validations*). Pendekatan DOM deklaratif (seperti React, Solid, Vue, atau Svelte) jauh lebih sedikit menimbulkan bug sinkronisasi state.
*   Proyek dengan siklus perubahan data bersarang (*deeply nested states*) yang rumit. Memanipulasi struktur DOM secara imperatif pada kasus ini akan menghasilkan *spaghetti code* dan sulit dilakukan *unit testing*.

---

### 15. Common Mistakes
1.  **Layout Thrashing Interleaving Loop**:
    ```javascript
    // KESALAHAN KRITIS: Baca - Tulis - Baca - Tulis
    elements.forEach(el => {
      const width = el.offsetWidth; // READ (Forced Reflow)
      el.style.width = `${width + 10}px`; // WRITE (Dirty Bit)
    });
    ```
2.  **String Concatenation pada `innerHTML` di Dalam Loop**:
    ```javascript
    // KESALAHAN FATAL: Memanggil HTML parser berulang kali dan menghancurkan seluruh child node lama
    for (let i = 0; i < 100; i++) {
      container.innerHTML += `<div>${i}</div>`; // O(n^2) cost!
    }
    ```
3.  **Detached DOM Memory Leak**:
    ```javascript
    let cachedButton = document.getElementById('btn');
    document.body.removeChild(cachedButton); 
    // Tombol sudah hilang dari layar, tetapi object C++ DOM node TIDAK DI-GARBAGE COLLECT 
    // karena variabel global `cachedButton` masih memegang referensinya di JS heap.
    ```
4.  **Tertukar antara `parentNode` vs `parentElement`**: Menggunakan `parentNode` saat mencari elemen pembungkus root dokumen dapat mengembalikan `Document` node, bukan `HTMLElement`, yang berpotensi menghasilkan error `undefined is not a function` ketika mengakses method khusus elemen.

---

### 16. Best Practices (Production Checklist)
*   [ ] **Pisahkan Mutasi (Read-Write Separation)**: Baca semua metrik geometri (`offsetHeight`, `clientWidth`, `getBoundingClientRect`) terlebih dahulu, simpan dalam variabel memori, baru jalankan seluruh mutasi style/DOM secara bersamaan.
*   [ ] **Gunakan `DocumentFragment`**: Untuk insersi elemen jamak, selalu tampung dalam `document.createDocumentFragment()` sebelum disisipkan ke DOM pohon aktif.
*   [ ] **Utamakan `replaceChildren()`**: Gunakan `element.replaceChildren(...nodes)` daripada `element.innerHTML = ''` untuk mengosongkan kontainer secara aman tanpa overhead alokasi memory leak HTML parser.
*   [ ] **Minimalkan Inline Style Changes**: Ubah tampilan visual dengan menambahkan/menghapus kelas CSS (`classList.toggle`, `classList.add`) dibanding memodifikasi `element.style` langsung satu per satu.
*   [ ] **Gunakan `insertAdjacentHTML` jika Perlu Parsing String**: Jika harus menyisipkan raw HTML, gunakan `container.insertAdjacentHTML('beforeend', str)` alih-alih merusak representasi internal dengan `innerHTML +=`.
*   [ ] **Dereference Objek DOM**: Setel variabel referensi elemen DOM ke `null` jika elemen terkait dihapus dari tampilan pohon secara permanen.

---

### 17. Troubleshooting

#### Masalah 1: Deteksi Warning "Forced reflow is a likely performance bottleneck" di Chrome DevTools
*   **Akar Masalah**: Terdapat script yang mengakses properti pemicu layout (misal: `scrollTop`, `getBoundingClientRect()`) segera setelah mengubah layout property (`width`, `height`, `margin`, `display`).
*   **Solusi**:
    1. Buka Chrome DevTools $\to$ Tab **Performance** $\to$ Lakukan Profiling saat interaksi berjalan.
    2. Cari bar berwarna merah ungu pada thread utama (*Main*).
    3. Klik warning "Layout", periksa *Call Stacks* yang mengarah langsung ke baris JS pembaca nilai layout.
    4. Pindahkan instruksi pembacaan ke awal method, atau tunda instruksi penulisan menggunakan `requestAnimationFrame`.

#### Masalah 2: Detached HTML Element Memory Leak
*   **Akar Masalah**: Elemen yang telah dihapus dari antarmuka via `.remove()` atau penimpaan container masih tertahan oleh penampung objek JavaScript atau event handler yang menempel (*retained size tinggi*).
*   **Solusi**:
    1. Buka DevTools $\to$ Tab **Memory** $\to$ Pilih **Heap snapshot** $\to$ Klik *Take snapshot*.
    2. Jalankan interaksi hapus elemen pada UI aplikasi.
    3. Ambil snapshot kedua, filter hasil berdasarkan string: `Detached HTMLDivElement` (atau elemen terkait).
    4. Periksa alur *Retainer Tree* di panel bawah untuk menemukan variabel referensi global atau *closure context* yang belum di-nullifikasi, lalu panggil `el = null` setelah operasi pelepasan DOM.

---

### 18. Exercise
Buatlah berkas JavaScript murni untuk menyelesaikan instruksi berikut:
1.  Buat fungsi `buildProductGrid(items)` yang menerima array berisi 500 objek produk `{ id: number, name: string, price: number }`.
2.  Gunakan `document.createDocumentFragment()` untuk merakit seluruh kartu produk tersebut ke dalam DOM.
3.  Setiap elemen produk harus memiliki class `.product-card`, judul produk dalam tag `<h3>`, dan harga dalam tag `<p>`.
4.  Lakukan pengukuran waktu komputasi pembuatan dan injeksi DOM menggunakan `console.time('DOM-Injection')` dan `console.timeEnd('DOM-Injection')`. Catat bahwa proses tidak boleh memakan waktu lebih dari 15ms pada CPU throttling standard.

---

### 19. Challenge
**Tantangan Rekayasa**: Bangun mekanisme Vanilla DOM Dynamic Batcher (`DOMBatcher`) berbentuk antrean (queue).

**Spesifikasi Persyaratan**:
*   Class `DOMBatcher` harus menyediakan method `.read(taskFn)` dan `.write(taskFn)`.
*   Semua task fungsi yang didaftarkan ke dalam `.read()` harus dieksekusi secara berurutan dalam fase pembacaan (*Measure Phase*).
*   Semua task yang didaftarkan ke dalam `.write()` harus ditunda dan dieksekusi secara bersamaan (*Mutate Phase*) pada frame render berikutnya menggunakan `window.requestAnimationFrame`.
*   Jika seorang developer mengeksekusi 10 kali pemanggilan `.read()` dan `.write()` secara acak selang-seling, class `DOMBatcher` harus menjamin bahwa sistem hanya mengeksekusi **satu kali** batch pembacaan dan **satu kali** batch penulisan tanpa memicu *Layout Thrashing* sedikit pun.

---

### 20. Summary
*   **DOM adalah Antarmuka Host Eksternal**: DOM tree merupakan struktur C++ di browser engine yang terhubung dengan V8 JS runtime melalui Web IDL binding layer; setiap operasi lintas batas memiliki biaya komputasi.
*   **Nodes vs Elements**: Hindari galat penelusuran dengan mengutamakan API keluarga Element (`children`, `firstElementChild`, `append`) daripada keluarga Node (`childNodes`, `firstChild`, `appendChild`) kecuali memang sengaja memproses teks atau komentar.
*   **Eliminasi Reflow Berantai**: Kunci performa DOM rendering adalah pemisahan ketat antara pembacaan metrik geometri dan penulisan perubahan tampilan. Hindari interleaved *read-write* layout properties.
*   **Atomik In-Memory Assembly**: Gunakan `DocumentFragment` sebagai panggung persiapan mutasi di memori sebelum menembus pipeline visual browser untuk menjamin kelancaran interaksi pada standar emas rendering 60 FPS ($16.6\text{ ms}$).