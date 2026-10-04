# Bab 07 Module 01: Arsitektur DOM, Manipulasi Node, dan Pola Event-Driven Native

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
*   Menganalisis representasi memori *Document Object Model* (DOM) pada *browser engine* (Blink/Gecko/WebKit) dan hubungannya dengan struktur HTML mentah.
*   Mengimplementasikan operasi manipulasi DOM (kueri, mutasi, penghapusan, traversal) dengan kompleksitas waktu minimal serta menghindari *Layout Thrashing* (*Forced Reflow*).
*   Merancang sistem penanganan *event* berbasis performa tinggi memanfaatkan fase *Capturing*, *Target*, dan *Bubbling* menggunakan pola *Event Delegation*.
*   Mendeteksi dan mengeliminasi *memory leaks* yang disebabkan oleh *dangling event listeners* dan referensi Node yang tidak ter-dereferensiasi oleh *Garbage Collector*.

---

### 2. Prerequisite
Untuk memahami materi ini secara komprehensif, Anda harus menguasai:
*   Sintaks inti JavaScript (ES6+): *Scope*, *Closures*, *Destructuring*, *Arrow Functions*, dan *Promises*.
*   Struktur HTML5 Semantik: Hubungan hierarki elemen *parent-child-sibling*.
*   CSS Rendering Pipeline dasar: Pemahaman mengenai *Critical Rendering Path* (Parse HTML $\rightarrow$ DOM Tree $\rightarrow$ CSSOM $\rightarrow$ Render Tree $\rightarrow$ Layout $\rightarrow$ Paint $\rightarrow$ Composite).

---

### 3. Concept
Secara arsitektural, peramban web (*browser*) tidak memanipulasi file HTML secara langsung. Browser memproses string HTML melalui *tokenization* dan *tree construction* untuk menghasilkan struktur data pohon berarah (*directed tree*) di dalam memori yang disebut **Document Object Model (DOM)**. 

Di balik layar, DOM direpresentasikan oleh objek C++ (misalnya pada Chromium/Blink, turunan dari kelas `Node` dan `Element`). JavaScript tidak berjalan di memori yang sama persis dengan modul rendering C++ tersebut; JavaScript beroperasi di atas V8 Engine. Interaksi antara JavaScript dan DOM terjadi melalui lapisan abstraksi yang disebut **C++ Bindings** (*V8-to-Blink bridge*). 

```
+-------------------------------------------------------------+
|                      Browser Process                        |
|                                                             |
|  +--------------------+             +--------------------+  |
|  |     V8 Engine      |   IPC /     |  Rendering Engine  |  |
|  |  (JavaScript VM)   |  Bindings   |  (Blink / WebKit)  |  |
|  |                    |<----------->|                    |  |
|  | JS Object Wrappers |             | C++ DOM Node Trees |  |
|  +--------------------+             +--------------------+  |
+-------------------------------------------------------------+
```

Konsekuensi arsitektur ini:
1.  **Boundary Crossing Cost**: Setiap kali JavaScript mengakses atau mengubah Node DOM via API browser (misal: `document.getElementById`), terdapat *overhead* transisi konteks antara JS Engine dan C++ DOM implementation. Operasi DOM massal secara individual selalu lebih lambat dibandingkan manipulasi struktur data JS murni.
2.  **Node Hierarchy**: Semua entitas di dalam DOM mewarisi antarmuka (`interface`) dari `EventTarget` $\rightarrow$ `Node` $\rightarrow$ `Element` $\rightarrow$ `HTMLElement`. Pemahaman hierarki ini krusial:
    *   `EventTarget`: Menyediakan metode `addEventListener`, `removeEventListener`, `dispatchEvent`.
    *   `Node`: Titik temu hierarkis (bisa berupa `Element`, `Text`, `Comment`, atau `DocumentFragment`).
    *   `Element`: Node spesifik yang merepresentasikan tag XML/HTML (memiliki atribut seperti `id`, `classList`, metode `querySelector`).
    *   `HTMLElement`: Elemen dengan kapabilitas rendering web (seperti `offsetWidth`, `style`, `hidden`).

---

### 4. Why
Memahami mekanisme native DOM dan sistem penanganan *event* adalah fondasi utama bagi perekayasa perangkat lunak web (*front-end engineers*), karena:
1.  **Mitigasi Bottleneck Performa Rendering**: Kerusakan performa web paling sering dipicu oleh pemanggilan API DOM yang memicu *Layout Thrashing* (rekalkulasi geometri secara sinkron berulang-ulang dalam satu frame siklus render 16.6ms).
2.  **Skalabilitas Memori (Leak Prevention)**: Menempelkan *event listener* pada ribuan elemen interaktif (misal: baris tabel atau kartu produk) menghabiskan memori heap secara masif. Pola *Event Delegation* mereduksi ratusan objek *listener* menjadi satu pengawas terpusat.
3.  **Memahami Abstraksi Framework Modern**: Framework tingkat tinggi seperti React, Vue, atau Svelte hanyalah lapisan abstraksi di atas API native ini (Virtual DOM / Direct Fine-Grained Reactive DOM). Tanpa pemahaman fondasi ini, arsitek perangkat lunak tidak dapat mengoptimalkan aplikasi ketika terjadi degradasi performa pada tingkat browser.

---

### 5. What
Komponen kunci yang terlibat dalam ekosistem manipulasi dan event DOM:

*   **`Document` & `DocumentFragment`**: Entry point DOM. `DocumentFragment` adalah kontainer DOM ringan di memori (*off-DOM*) yang tidak terikat pada *Render Tree*, ideal untuk operasi *batch insertion* tanpa memicu *reflow*.
*   **Selectors API**: `querySelector()` dan `querySelectorAll()`. Mengembalikan representasi statis (*static NodeList*) yang di-query menggunakan sintaks CSS selector. Berbeda dengan metode lawas `getElementsByClassName` yang mengembalikan *live HTMLCollection*.
*   **Mutation APIs**: `append()`, `prepend()`, `replaceWith()`, `remove()` (API modern), serta `appendChild()`, `removeChild()`, `insertBefore()` (API klasik).
*   **The Event Model (`EventTarget`)**:
    *   **Fase Capturing (Trickling)**: Event turun dari `window` melewati `document`, `<html>`, `<body>`, hingga mencapai parent langsung dari target.
    *   **Fase Target**: Event dieksekusi pada target spesifik yang memicu aksi (`event.target`).
    *   **Fase Bubbling**: Event memantul kembali ke atas dari target menuju `window`.
*   **Event Interface**: Objek yang dikirim ke listener; membawa metadata penting seperti `e.target` (elemen sumber), `e.currentTarget` (elemen pemilik listener), `e.preventDefault()`, dan `e.stopPropagation()`.

---

### 6. How
Alur pemrosesan event dan mutasi DOM berjalan sebagai berikut:

#### Siklus Hidup Event Propagation:
1.  Pengguna memicu input periferal (contoh: klik mouse pada tombol di dalam form).
2.  Hardware interrupt diterjemahkan OS $\rightarrow$ diteruskan ke Browser Process $\rightarrow$ Browser Engine mendeteksi koordinat layar.
3.  **Hit-testing**: Browser mencari elemen visual terdalam yang berada di titik koordinat tersebut. Elemen ini ditetapkan sebagai `Event.target`.
4.  Engine menyusun *propagation path* dari root `Window` sampai `target`.
5.  **Capture Phase**: Browser mengeksekusi listener yang didaftarkan dengan flag `{ capture: true }` dari atas ke bawah.
6.  **Target Phase**: Eksekusi listener yang terdaftar langsung pada node target.
7.  **Bubble Phase**: Browser mengeksekusi listener yang didaftarkan dengan flag standar `{ capture: false }` secara mundur ke atas sampai ke `Window`.

```
                | |               / \
 1. CAPTURE     | |               | | 3. BUBBLE
    PHASE       | |   WINDOW      | |    PHASE
                | |      |        | |
                | |   DOCUMENT    | |
                | |      |        | |
                | |    BODY       | |
                | |      |        | |
                v |    DIV        | /
                  +------+--------+
                         |
                 2. TARGET PHASE
                   (BUTTON CLICKED)
```

#### Alur Manipulasi Optimal (Batch Mutation):
1.  Hindari menyisipkan elemen ke DOM aktif satu per satu dalam perulangan (*looping*).
2.  Instansiasi `DocumentFragment` di memori.
3.  Lakukan konstruksi hierarki elemen secara penuh di dalam fragment.
4.  Sematkan `DocumentFragment` ke dalam target DOM aktif melalui satu operasi pemanggilan API (misal: `parent.appendChild(fragment)`).
5.  Browser merealisasikan mutasi secara atomik, hanya memicu 1 kali kalkulasi *Style Calculation* dan *Layout Tree generation*.

---

### 7. Analogy
Bayangkan sebuah **Gedung Perkantoran Multi-Lantai**:
*   **DOM Tree** adalah struktur fisik gedung: Lantai teratas (Root/Window) membawahi Departemen (Div), membawahi Ruangan (Section), membawahi Meja Kerja (Button).
*   **Manipulasi DOM Langsung** seperti merenovasi meja secara individual di lokasi kerja. Jika Anda memasang 100 meja satu per satu langsung di ruangan kantor, alarm kebisingan dan penataan ulang rute evakuasi (*Reflow & Repaint*) akan berbunyi 100 kali, mengganggu seluruh operasional kantor. Menggunakan `DocumentFragment` setara dengan merakit 100 meja di gudang terpisah (*off-DOM*), lalu memasukkannya secara bersamaan dalam satu kali pengiriman logistik.
*   **Event Bubbling & Delegation** seperti sistem surat interkom. Alih-alih menempatkan satu kurir pos (*listener*) di setiap meja staf (ratusan meja), kantor hanya menempatkan **satu kurir pos di pintu masuk departemen** (*parent listener*). Ketika seorang staf di meja tertentu (*event.target*) mengirim surat, dokumen tersebut secara hierarkis dinaikkan ke meja manajer di lantai tersebut (*bubbling*). Sang kurir cukup memeriksa identitas staf pengirim pada label surat lalu mengeksekusi tugas.

---

### 8. Diagram
Diagram alir eksekusi Event Delegation dan arsitektur propagasi:

```
[Window]
   │
   ▼ (1. Capturing Phase)
[Document]
   │
   ▼
[HTML]
   │
   ▼
[Body]
   │
   ▼
[UL id="task-list"]  <── [EVENT LISTENER REGISTERED HERE (Delegation)]
   │                     │
   │ (Capturing...)      │ (4. Handles event dynamically by verifying
   ▼                     │     e.target == "BUTTON.delete-btn")
[LI class="task-item"]   │
   │                     │
   ▼ (2. Target Hit)     │ (3. Bubbles upward)
[BUTTON class="delete-btn"] ──┘
```

---

### 9. Simple Example
Dasar seleksi elemen, pembuatan elemen, dan eksekusi event:

```javascript
// 1. Kueri elemen root kontainer
const container = document.querySelector('#app-container');

// 2. Pembuatan elemen secara programatis di memori
const alertBox = document.createElement('div');
alertBox.classList.add('alert', 'alert-info');
alertBox.setAttribute('role', 'alert');
alertBox.textContent = 'Data berhasil dimuat dari sistem.';

// 3. Penambahan interaktivitas
const closeButton = document.createElement('button');
closeButton.textContent = 'Tutup';
closeButton.style.marginLeft = '8px';

// Mendaftarkan event listener pada fase bubbling standar
closeButton.addEventListener('click', (event) => {
  console.log('Target penekanan:', event.target);
  alertBox.remove(); // Menghapus alertBox dari DOM
});

// 4. Injeksi ke tree aktif
alertBox.appendChild(closeButton);
container.appendChild(alertBox);
```

---

### 10. Practical Example
Aplikasi Pengelola Inventaris Dinamis (Task Manager) dengan pola **Event Delegation**, pencegahan **Memory Leaks**, dan **Batch Injection** yang meminimalkan *Reflow*.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>High Performance DOM Delegation</title>
  <style>
    .completed { text-decoration: line-through; color: #888; }
    .item { display: flex; gap: 8px; margin: 4px 0; }
  </style>
</head>
<body>
  <div id="root">
    <form id="todo-form">
      <input type="text" id="todo-input" placeholder="Nama tugas..." required />
      <button type="submit">Tambah</button>
    </form>
    <button id="batch-add">Tambah 1000 Item (Batch)</button>
    <ul id="todo-list"></ul>
  </div>

  <script>
    class TodoManager {
      constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.listElement = this.container.querySelector('#todo-list');
        this.formElement = this.container.querySelector('#todo-form');
        this.inputElement = this.container.querySelector('#todo-input');
        this.batchBtn = this.container.querySelector('#batch-add');

        this.init();
      }

      init() {
        // Event listener lokal untuk form submit
        this.formElement.addEventListener('submit', (e) => this.handleSubmit(e));

        // Event listener lokal untuk batch processing
        this.batchBtn.addEventListener('click', () => this.handleBatchInsert());

        // EVENT DELEGATION: Listener tunggal untuk seluruh aksi di child elements
        // Menangani aksi Click baik untuk 'hapus' maupun 'toggle-complete'
        this.listElement.addEventListener('click', (e) => this.handleListAction(e));
      }

      createItemNode(id, text) {
        const li = document.createElement('li');
        li.className = 'item';
        li.dataset.id = id;

        const span = document.createElement('span');
        span.textContent = text;
        span.className = 'item-text';

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.dataset.action = 'toggle';
        toggleBtn.textContent = 'Selesai';

        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.dataset.action = 'delete';
        deleteBtn.textContent = 'Hapus';

        li.append(span, toggleBtn, deleteBtn);
        return li;
      }

      handleSubmit(e) {
        e.preventDefault();
        const value = this.inputElement.value.trim();
        if (!value) return;

        const newItem = this.createItemNode(Date.now().toString(), value);
        this.listElement.appendChild(newItem);
        this.inputElement.value = '';
      }

      // Injeksi masif dengan performa O(1) Reflow menggunakan DocumentFragment
      handleBatchInsert() {
        const fragment = document.createDocumentFragment();
        const timestamp = Date.now();

        for (let i = 0; i < 1000; i++) {
          const itemNode = this.createItemNode(
            `${timestamp}-${i}`, 
            `Tugas Generasi Massal #${i + 1}`
          );
          fragment.appendChild(itemNode);
        }

        // Tepat 1 kali pemicuan Layout/Reflow terjadi di sini
        this.listElement.appendChild(fragment);
      }

      // Router delegasi event
      handleListAction(e) {
        const target = e.target;
        
        // Memeriksa apakah target memiliki data-action
        const action = target.dataset.action;
        if (!action) return;

        // Cari parent node 'LI' terdekat
        const itemNode = target.closest('li.item');
        if (!itemNode || !this.listElement.contains(itemNode)) return;

        switch (action) {
          case 'delete':
            this.deleteItem(itemNode);
            break;
          case 'toggle':
            this.toggleComplete(itemNode);
            break;
        }
      }

      deleteItem(itemNode) {
        // Element.remove() modern memutus referensi dari parent DOM
        itemNode.remove();
      }

      toggleComplete(itemNode) {
        const textSpan = itemNode.querySelector('.item-text');
        textSpan.classList.toggle('completed');
      }

      // Cleanup method untuk mencegah dangling reference jika UI dihancurkan
      destroy() {
        this.listElement.replaceChildren(); // Bersihkan DOM child
        // Menghapus referensi agar garbage collector membersihkan listener
        this.formElement = null;
        this.listElement = null;
        this.inputElement = null;
      }
    }

    // Instansiasi komponen
    const app = new TodoManager('#root');
  </script>
</body>
</html>
```

---

### 11. Real World Example
#### Kasus Produksi: Infinite Feed List pada Platform E-Commerce / Media Sosial
Pada aplikasi skala besar seperti feed media sosial (Twitter/Instagram) atau katalog produk tak terbatas (Tokopedia/Amazon), pengguna berinteraksi dengan puluhan ribu item visual (tombol like, tombol share, kartu produk).

**Pendekatan Amatir (Naive):**
Setiap kali data produk baru di-*fetch* melalui REST/GraphQL API, peramban me-render kartu dan menambahkan listener langsung:
```javascript
productCard.querySelector('.btn-like').addEventListener('click', handleLike);
productCard.querySelector('.btn-buy').addEventListener('click', handleBuy);
```
Jika pengguna melakukan *infinite scroll* hingga 5.000 produk, browser harus mengalokasikan memori untuk minimal $5.000 \times 2 = 10.000$ objek listener terpisah. Hasilnya:
*   Alokasi Memori V8 membengkak puluhan Megabyte.
*   *Garbage Collection pause* (GC stutters) terjadi saat *scrolling*, menyebabkan frame rate drop di bawah 60 FPS (*jank*).

**Pendekatan Arsitektur Standar Industri (Engineered Pattern):**
1.  **Virtual Scrolling / DOM Recycling**: Hanya merender elemen yang tampak di *viewport* ditambah *buffer zone* (misal: hanya merender 30 node aktif).
2.  **Centralized Event Delegation**: Seluruh interaksi diikat pada kontainer feed utama (`#feed-container`).
3.  Ketika event *click* terjadi di manapun di dalam feed, event berpropagasi (*bubbles up*) ke `#feed-container`. Satu fungsi membaca metadata via atribut HTML data (`dataset.productId`, `dataset.action`) dan mengeksekusi *state store/service dispatch*. Memori heap listener tetap konstan: **O(1)** terlepas dari berapa kali pengguna menggulir halaman.

---

### 12. Trade-offs

| Aspek | Pendaftaran Listener Individual | Pola Event Delegation | Batching via `DocumentFragment` | Direct Mutation (`appendChild` in loop) |
| :--- | :--- | :--- | :--- | :--- |
| **Konsumsi Memori** | **Tinggi ($O(N)$)**: Alokasi memory-leak risk tinggi | **Sangat Rendah ($O(1)$)**: Hanya 1 listener di parent | **Minimal**: Dibuat lalu dibersihkan GC | **Rendah**: Tapi beban thread engine tinggi |
| **Kompleksitas Kode** | **Rendah**: Langsung bind ke target | **Sedang**: Perlu validasi `e.target` / `closest()` | **Rendah**: API standar web | **Sangat Rendah**: Naive |
| **Performa Rendering** | Tidak terpengaruh langsung (fokus di event) | Optimal (mengurangi tekanan CPU GC) | **Tinggi**: 1 Reflow Cycle per batch | **Kritis (Buruk)**: Memvalidasi layout berulang kali |
| **Dukungan Dynamic Content** | **Buruk**: Elemen baru butuh registrasi manual | **Sempurna**: Otomatis menangani elemen yang baru disuntik | N/A | N/A |
| **Penanganan Event Spesifik** | Mendukung semua event | Event harus ber-gelembung (*bubble*). Tidak berlaku untuk `focus`/`blur` (gunakan `focusin`/`focusout`) | N/A | N/A |

---

### 13. When To Use
Gunakan manipulasi DOM imperatif dan delegasi tingkat lanjut saat:
*   Membangun komponen dasar performa tinggi yang tidak memerlukan re-render seluruh aplikasi (misal: Canvas overlay controls, custom video player controls).
*   Merender daftar dinamis dengan jumlah baris yang tidak terbatas (*infinite scrolling*, *data tables* besar).
*   Membangun pustaka pihak ketiga (*third-party libraries/widgets*) berbasis Vanilla JS murni agar *bundle size* kecil dan bebas ketergantungan *framework*.
*   Menangani elemen HTML dinamis yang strukturnya di-generate di runtime melalui template string atau Web Components.

---

### 14. When NOT To Use
Hindari manipulasi DOM imperatif secara manual ketika:
*   Membangun antarmuka berbasis *state* yang kompleks di mana puluhan elemen saling terikat secara reaktif. Gunakan pustaka berbasis deklaratif (React, Vue, SolidJS) agar sinkronisasi state dan visual terjamin prediktabilitasnya.
*   Mengontrol elemen yang siklus hidupnya dikelola sepenuhnya oleh *Virtual DOM* dari framework; mencampuradukkan manipulasi DOM native langsung ke dalam komponen framework dapat merusak rekonsiliasi (*reconciliation sync breakdown*).
*   Aplikasi berorientasi form entri enterprise dengan ratusan validasi real-time; pendekatan deklaratif berbasis data model jauh lebih *maintainable*.

---

### 15. Common Mistakes
1.  **Layout Thrashing (Forced Synchronous Layout):**
    Membaca dimensi geometri lalu langsung menulis ke DOM dalam satu loop.
    ```javascript
    // KESALAHAN FATAL: Membaca (offsetHeight) memicu layout sinkron seketika,
    // lalu menulis (style.height) membatalkan layout tersebut.
    elements.forEach(el => {
      const height = el.offsetHeight; // READ
      el.style.height = (height + 10) + 'px'; // WRITE
    });
    
    // PERBAIKAN: Pisahkan fase READ dan WRITE
    const heights = elements.map(el => el.offsetHeight); // Batch READ
    elements.forEach((el, i) => {
      el.style.height = (heights[i] + 10) + 'px'; // Batch WRITE
    });
    ```
2.  **Mengabaikan Event Non-Bubbling pada Delegation:**
    Mencoba mendelegasikan event `blur` atau `focus` secara konvensional. Kedua event ini tidak menembus fase bubbling (`bubbles: false`). 
    *Solusi:* Gunakan event padanannya yang mendukung bubbling, yaitu `focusin` dan `focusout`.
3.  **Memory Leaks via Node Reference Retention:**
    Menghapus elemen dari tampilan tetapi tetap menyimpannya di variabel global:
    ```javascript
    let btn = document.getElementById('heavy-button');
    btn.remove(); // Dihapus dari DOM Tree, TETAPI tetap ada di JS Heap memory
    // Perbaikan: Hapus referensi agar garbage collector bekerja
    btn = null;
    ```

---

### 16. Best Practices (Production Checklist)
*   [ ] **Gunakan `textContent` alih-alih `innerHTML`** jika hanya menyisipkan teks, guna mengeliminasi vektor kerentanan serangan *Cross-Site Scripting (XSS)* dan memotong parser HTML engine.
*   [ ] **Gunakan `Element.closest(selector)`** dalam *Event Delegation* untuk menemukan ancestor relevan terdekat dengan aman saat user menekan anak terdalam elemen (misal: icon SVG di dalam button).
*   [ ] **Gunakan flag `{ passive: true }`** pada event penanganan sentuhan (*touch*) atau pengguliran (*wheel/scroll*) jika tidak memanggil `e.preventDefault()`. Ini memberitahu browser thread untuk segera melakukan composite tanpa menunggu JS selesai dieksekusi:
    ```javascript
    window.addEventListener('scroll', onScroll, { passive: true });
    ```
*   [ ] **Pilih `querySelectorAll` atau `getElementById` secara bijak**: `getElementById` beroperasi pada hash map C++ dengan kompleksitas $O(1)$, sedangkan query selector kompleks mengeksekusi evaluasi CSS Engine parser.
*   [ ] **Gunakan `DocumentFragment`** untuk batch mutasi DOM off-screen.
*   [ ] **Daftarkan listener dengan flag `{ once: true }`** jika event tersebut hanya perlu dieksekusi satu kali seumur hidup aplikasi, sehingga pembersihan listener ditangani otomatis oleh browser runtime.

---

### 17. Troubleshooting

#### Masalah: "Tombol di dalam elemen tidak merespons Event Delegation saat anak elemen (seperti SVG/Icon) ditekan."
*   **Gejala:** Listener mengecek `if (e.target.classList.contains('my-btn'))`, namun bernilai `false` karena `e.target` yang tertangkap adalah `<path>` atau `<span>` di dalam button.
*   **Akar Masalah:** `e.target` merujuk ke elemen visual terdalam yang disentuh kursor (leaf node).
*   **Resolusi:**
    ```javascript
    parent.addEventListener('click', (e) => {
      // Menavigasi ke atas sampai menemukan .my-btn atau null
      const button = e.target.closest('.my-btn');
      if (!button || !parent.contains(button)) return;
      
      // Eksekusi logic dengan target tombol yang valid
      console.log('Button ID:', button.dataset.id);
    });
    ```

#### Masalah: "Aplikasi lambat secara progresif (Frame Rate Degradation) setelah navigasi berulang."
*   **Gejala:** Memory DevTools menunjukkan alokasi *Detached HTMLCanvasElement* atau *Detached HTMLElement* yang terus mendaki.
*   **Akar Masalah:** Komponen dihapus dari dokumen via `element.remove()`, namun listener-nya masih menempel pada objek global (`window` atau `document`), atau masih ada closure yang menyimpan referensi ke node yang telah dicopot tersebut.
*   **Resolusi:** Selalu pasangkan pendaftaran listener dengan pembatalan listener via `removeEventListener` ketika elemen induk dihancurkan, atau manfaatkan `AbortController`:
    ```javascript
    const controller = new AbortController();
    
    window.addEventListener('resize', handleResize, { signal: controller.signal });
    
    // Ketika komponen dihancurkan (unmount):
    controller.abort(); // Secara otomatis melepas seluruh listener yang terhubung
    ```

---

### 18. Exercise
**Instruksi Tugas Mandiri:**
Bangun sebuah modul JavaScript murni untuk menampilkan daftar log aktivitas (*Real-time Activity Feed*).

1.  Buat file `index.html` dengan kontainer `#feed-container` dan tombol `#clear-all`.
2.  Tulis fungsi `injectLog(type, message)`:
    *   Tipe log: `INFO`, `WARN`, `ERROR`.
    *   Setiap item harus memiliki elemen teks deskripsi, penanda waktu (*timestamp*), dan tombol aksi "Detail" serta "Arsipkan".
3.  Terapkan **Event Delegation** pada `#feed-container`:
    *   Jika tombol "Arsipkan" diklik, hapus baris yang bersangkutan dari DOM tanpa memicu error traversal.
    *   Jika tombol "Detail" diklik, ubah warna background baris menjadi `#f0f0f0` menggunakan manipulasi *CSS class* (`classList.toggle`), bukan manipulasi `element.style` inline.
4.  Pastikan tidak ada deklarasi `addEventListener` langsung pada node item log baru.

---

### 19. Challenge
**Tantangan Arsitektur:** Rancang sebuah sistem tabel data dinamis (*Interactive Data Grid*) Vanilla JS yang mampu meng-handle **10.000 baris data** tanpa frame-rate drop (wajib menjaga rendering minimal di 60 FPS saat pemuatan dan pengurutan/sorting).

**Kriteria Wajib:**
1.  **Virtualization Lite / Batching Strategy**: Dilarang melakukan injeksi 10.000 elemen `<tr>` secara sinkron langsung ke `<tbody>`. Gunakan kombinasi `DocumentFragment` dan penjadwalan via `requestAnimationFrame` untuk memotong proses chunk injection (misal: 200 baris per frame).
2.  **Zero-Leak Delegation System**: Semua operasi baris (edit inline saat double-click, checkbox selection, tombol action baris) hanya boleh dikelola oleh **1 listener** di tingkat `<table>`.
3.  **Measurement Check**: Buktikan bahwa waktu eksekusi skrip (*script evaluation time*) di tab Performance Chrome DevTools tidak melampaui ambang batas 50ms (mencegah *Long Task*).

---

### 20. Summary
*   **DOM adalah Abstraksi Tingkat Tinggi**: DOM merupakan representasi berakar C++ di memori yang dijembatani ke runtime JavaScript via V8 Bindings. Setiap akses ke DOM membawa *overhead* eksekusi.
*   **Siklus Propagasi Event**: Event merambat melalui tiga fase: *Capture Phase* (dari root ke leaf), *Target Phase*, dan *Bubble Phase* (dari leaf memantul kembali ke root).
*   **Pola Event Delegation**: Mengonsolidasi manajemen event ke elemen leluhur (*ancestor*), mengubah kompleksitas registrasi memori dari $O(N)$ menjadi $O(1)$, serta mendukung elemen baru yang disuntikkan secara dinamis secara otomatis.
*   **Efisiensi Mutasi DOM**: Selalu minimalkan *Layout Thrashing* dengan memisahkan fase pembacaan (*READ*) dan penulisan (*WRITE*). Gunakan `DocumentFragment` untuk menyusun sekumpulan node di luar memori layar aktif (*off-DOM*) sebelum mengeksekusi mutasi tunggal.