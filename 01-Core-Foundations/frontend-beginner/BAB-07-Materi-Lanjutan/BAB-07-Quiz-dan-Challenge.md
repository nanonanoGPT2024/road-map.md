# BAB 07: Quiz, Challenge, & Knowledge Check
**Manipulasi DOM Lanjutan & Event-Driven Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Siklus Hidup Event Propagation (Capturing, Target, Bubbling):**  
   Jelaskan secara mendalam alur traversal event dari `Window` hingga mencapai elemen target dan kembali ke root. Mengapa arsitektur *Event Delegation* hampir selalu memanfaatkan fase *bubbling* alih-alih *capturing*, dan dalam skenario teknis spesifik apa Anda wajib mengaktifkan opsi `{ capture: true }`?

2. **Perbedaan Struktural `Node`, `Element`, dan Koleksi DOM:**  
   Bedakan secara fundamental antara `NodeList` (statis vs live) dan `HTMLCollection`. Mengapa mutasi DOM massal menggunakan `element.appendChild()` di dalam loop memicu degradasi performa render secara drastis dibanding menggunakan `DocumentFragment` atau metode `element.append()` modern?

3. **Integritas Konteks Event: `target` vs `currentTarget` vs `relatedTarget`:**  
   Analisis perbedaan teknis antara `event.target`, `event.currentTarget`, dan `event.relatedTarget` (pada event seperti `mouseenter`/`mouseleave` atau `focusout`). Apa implikasi fatalnya jika seorang engineer salah mereferensikan `target` alih-alih `currentTarget` saat mengimplementasikan pola *Event Delegation* pada elemen bersarang (*nested components*)?

4. **Mekanisme Eksekusi: `stopPropagation()` vs `stopImmediatePropagation()` vs `preventDefault()`:**  
   Uraikan implikasi arsitektural dari ketiga metode ini pada thread eksekusi browser. Jika sebuah elemen memiliki 3 listener berbeda untuk event `click` yang didaftarkan oleh pustaka (*library*) yang independen, apa yang terjadi pada listener ke-2 dan ke-3 jika listener ke-1 mengeksekusi `e.stopImmediatePropagation()` dibandingkan dengan `e.stopPropagation()`?

5. **Optimasi Thread Rendering dengan Passive Event Listeners:**  
   Jelaskan bagaimana argumen `{ passive: true }` pada `addEventListener` mencegah pemblokiran *Compositor Thread* pada event berfrekuensi tinggi seperti `touchstart`, `touchmove`, atau `wheel`. Masalah arsitektur apa yang terjadi jika kode di dalam listener pasif tetap memanggil `event.preventDefault()`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Deteksi dan Mitigasi *Detached DOM Nodes Memory Leak*:**  
   Sebuah single-page navigation vanilla script menghapus elemen container dari DOM menggunakan `container.remove()`. Namun, penggunaan memori (Heap Allocation) di Chrome DevTools terus meningkat setiap kali navigasi terjadi. Jelaskan bagaimana referensi closure di dalam listener yang belum dilepas menyebabkan elemen tetap berstatus *Detached HTMLElement*, dan tunjukkan cara mitigasi modern menggunakan `AbortController` (`{ signal }`).

2. **Diagnostik *Layout Thrashing* (Forced Synchronous Layout):**  
   Periksa potongan alur kode berikut:
   ```javascript
   elements.forEach(el => {
       const width = el.getBoundingClientRect().width; // Read
       el.style.width = (width + 10) + 'px';           // Write
   });
   ```
   Jelaskan siklus internal rendering engine browser (Parse HTML -> Style Recalculation -> Layout/Reflow -> Paint -> Composite) saat baris tersebut dieksekusi. Mengapa pola *interleaving* (Read-Write berulang) ini menyebabkan *frame drop* (jank), dan bagaimana cara restrukturisasinya menggunakan batching via `requestAnimationFrame`?

3. **Edge Case Event Delegation pada Nested Complex Target:**  
   Sebuah tombol didefinisikan sebagai berikut: `<button data-action="delete"><svg><path d="..."/></svg><span>Hapus</span></button>`. Ketika pengguna mengklik ikon SVG, `event.target` merujuk ke elemen `SVGPathElement`, bukan `<button>`. Jelaskan mengapa pengecekan sederhana `if (e.target.dataset.action === 'delete')` gagal beroperasi, dan bagaimana metode `Element.prototype.closest()` menyelesaikan masalah perambatan naik hierarki secara performan.

4. **Transisi Arsitektur: *MutationObserver* vs *Mutation Events*:**  
   Mengapa *Mutation Events* lawas (seperti `DOMNodeInserted`) didepresiasi secara global oleh komite W3C/WHATWG karena memicu degradasi performa ekstrem? Jelaskan bagaimana penjadwalan berbasis *microtask* pada `MutationObserver` mengoptimalkan pemantauan perubahan DOM secara batch dan non-blocking terhadap thread UI utama.

5. **Event-Driven Decoupling: DOM CustomEvent vs Native Pub/Sub:**  
   Bandingkan arsitektur komunikasi komponen menggunakan `CustomEvent` (`window.dispatchEvent` dengan properti `detail` dan `{ bubbles: true }`) dibandingkan dengan kelas *In-Memory Event Emitter / Pub-Sub*. Apa *trade-off* utama terkait skalabilitas, memori, isolasi *headless environment* (misal: Unit Testing Jest tanpa DOM), dan *event boundary scoping*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck & Render Jank pada Live Trading Dashboard
* **Konteks:** Sebuah dashboard finansial menerima update harga saham via WebSocket dengan frekuensi 50 pesan per detik. Setiap pesan memicu pembaruan DOM pada tabel yang berisi 500 baris. Implementasi awal memperbarui atribut `innerHTML` atau memanipulasi `textContent` dan `classList` baris tabel secara langsung setiap kali paket data diterima.
* **Insiden:** Browser klien mengalami utilisasi CPU hingga 100%, animasi CSS terhenti total (*freezing*), responsivitas tombol UI drop hingga lebih dari 1500ms (*Total Blocking Time* ekstrem), dan Chrome DevTools Performance tab menunjukkan ribuan baris *Style Recalculation* berturut-turut.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah pada rendering pipeline browser dan mengapa pembaruan berbasis event streaming langsung ke DOM adalah antipattern.
  2. Rancang arsitektur buffering dan throttling menggunakan *Virtual DOM-less batching* (misal: penggabungan data masuk ke antrean memory, dan flush render yang disinkronisasi dengan monitor refresh rate via `requestAnimationFrame`).

### Skenario B: Race Condition dan State Desynchronization pada Form Wizard Asinkron
* **Konteks:** Sebuah sistem onboarding multi-langkah (*multi-step wizard*) menggunakan event-driven architecture di mana setiap perpindahan tab menembakkan custom event `step:change`. Saat berpindah dari Step 2 ke Step 3, sebuah request AJAX asinkron dikirim untuk memvalidasi data Step 2. Pengguna mengklik tombol "Next" secara cepat dua kali berturut-turut (atau menekan "Back" kemudian "Next" seketika).
* **Insiden:** Data Step 3 dirender sementara respons validasi Step 2 yang terlambat datang menimpa DOM Step 3 dengan pesan error Step 2. Event listener untuk validasi Step 2 tereksekusi pada elemen Step 3 yang memiliki class name serupa, menyebabkan formulir terkunci (*deadlock*).
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda mengisolasi lifecycle event antar-langkah agar event dari step sebelumnya tidak mencemari container step berikutnya?
  2. Implementasikan pola pembatalan transisi menggunakan kombinasi `AbortController` (untuk network request dan listener cleanup) serta state tracking berbasis status finite (*Idle, Validating, Transitioning*) guna mencegah eksekusi event yang *out-of-sync*.

### Skenario C: Architectural Trade-off: Monolithic Event Delegation vs Isolated Component Listeners
* **Konteks:** Tim frontend Anda membangun sistem e-commerce berskala enterprise. Terdapat perdebatan arsitektur internal antara dua Staff Engineer:
  * **Pendekatan 1:** Mendaftarkan satu *Global Event Listener* tunggal pada `document.body` untuk semua interaksi (klik tombol, input form, modal toggle) dengan routing berbasis `data-attribute` (misal: `data-action="open-cart"`).
  * **Pendekatan 2:** Setiap komponen bertanggung jawab penuh mendaftarkan dan membersihkan event listener-nya sendiri secara terisolasi pada root elemen komponen tersebut saat komponen di-mount dan di-unmount.
* **Pertanyaan Diagnostik:**
  1. Analisis performa, footprint memori, maintainability, risiko *single point of failure*, dan kemudahan *debugging* dari kedua pendekatan tersebut.
  2. Kriteria arsitektural spesifik apa yang menentukan kapan tim Anda harus memilih Pendekatan 1, dan kapan wajib beralih ke Pendekatan 2?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Event-Driven Task Board (Vanilla JS)

#### 1. Problem Statement
Bangun modul *Task Board* (seperti Kanban board sederhana) menggunakan **Pure Vanilla JavaScript (ESNext)** yang mampu menangani setidaknya 1.000 task cards tanpa *render lag*, mendukung operasi real-time (tambah, edit status via klik, hapus massal), dan memiliki arsitektur komunikasi berbasis event yang *loosely coupled* tanpa framework eksternal.

#### 2. Technical Requirements
1. **Event Delegation Pattern:**
   * Dilarang keras mendaftarkan `addEventListener` pada setiap individual task card.
   * Seluruh aksi kartu (hapus kartu, toggle prioritas, edit teks inline) harus dikelola secara terpusat pada tingkat kolom (Board Column) memanfaatkan teknik event delegation dan resolusi target menggunakan `closest()`.
2. **Unified Event-Driven Communication:**
   * Bangun modul terisolasi bernama `EventBus` atau manfaatkan `CustomEvent` yang ter-bubble untuk sinkronisasi state.
   * Setiap kali sebuah task dimutasi (misal: dipindahkan dari kolom "Backlog" ke "Done"), sistem harus menerbitkan event `task:stateChange` yang membawa payload metadata yang valid.
   * Modul terpisah (misal: modul `MetricsCounter` yang menghitung total task di pojok layar) harus merespons event tersebut tanpa dependensi langsung ke modul papan board (*decoupled*).
3. **Optimized Batch Rendering:**
   * Operasi penambahan massal (misal: load 500 initial tasks) harus menggunakan `DocumentFragment` atau template cloning.
   * Operasi update visual tidak boleh memicu *Layout Thrashing*. Pisahkan fase kalkulasi data (*Read*) dan update DOM (*Write*).
4. **Lifecycle & Memory Management:**
   * Buat fungsi destruktor: `destroy()`. Saat modul dihancurkan, seluruh listener harus otomatis ter-deregister tanpa meninggalkan *detached nodes* atau *retained listeners* di memori. Gunakan `AbortController` untuk pembatalan grup event listener.

#### 3. Constraints
* **Zero External Dependencies:** Tidak boleh menggunakan jQuery, React, Vue, Lodash, atau pustaka eksternal lainnya.
* **Security Standards:** Dilarang menggunakan `innerHTML` secara naif saat merender input pengguna (wajib mitigasi bahaya XSS menggunakan `textContent`, `document.createElement`, atau sanitasi DOM manual yang ketat).
* **Performance Budget:** Eksekusi render 500 item tidak boleh memakan waktu lebih dari 16.67ms pada thread utama (harus mempertahankan 60 FPS).

#### 4. Expected Output & Code Blueprint
Anda diminta menyusun arsitektur kode terstruktur yang mencakup:
* Kelas/Objek `TaskBoardComponent`.
* Definisi kontrak custom event (`TaskEvents`).
* Implementasi registrasi event terpusat via `AbortController`.
* Skema manipulasi batch DOM yang lolos audit performa Chrome DevTools.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi propagasi event W3C: fase capturing, target, dan bubbling beserta arah perambatannya.
- [ ] Perbedaan esensial antara `event.target` (inisiasi klik) dan `event.currentTarget` (pemilik listener aktif).
- [ ] Penyebab mekanis *Forced Synchronous Layout* / *Layout Thrashing* dan dampaknya terhadap frame rate monitor.
- [ ] Karakteristik *detached DOM elements* dan mekanika garbage collector V8 dalam menahan memori akibat referensi closure di event listener.
- [ ] Cara kerja queue browser: sinkronisasi rendering thread dengan microtask queue (`MutationObserver`) dan macrotask queue (timer, default events).
- [ ] Peran dan implementasi parameter opsi listener: `{ capture: boolean, once: boolean, passive: boolean, signal: AbortSignal }`.

### Saya tidak perlu menghafal:
- [ ] Seluruh kode numerik legacy untuk mouse button atau keyboard event (`which`, `keyCode`); gunakan `event.key` dan `event.code`.
- [ ] Sintaks mutasi DOM era IE lama seperti `attachEvent()`, `detachEvent()`, atau properti `srcElement`.
- [ ] Urutan parameter detail dari API DOM legacy yang terdepresiasi seperti `document.createEvent()`.
- [ ] Seluruh nama event spesifik web APIs tingkat lanjut (WebRTC, MIDI); cukup pahami pola konsumsi `addEventListener`.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *Event Delegation* yang robust dengan resolusi hierarki bersarang menggunakan `Element.prototype.closest()`.
- [ ] Membatalkan sekumpulan event listener secara instan dan bersih dalam satu pemanggilan metode menggunakan `AbortController`.
- [ ] Melakukan profiling render di Chrome DevTools (Performance & Memory Panel) untuk mendeteksi *Long Tasks*, *Recalculate Style*, dan *Heap Leaks*.
- [ ] Mengonstruksi alur komunikasi asinkron berbasis `CustomEvent` dengan payload tipe aman (*safe payload dispatching*).
- [ ] Memanipulasi ribuan elemen DOM tanpa memicu jank UI dengan memanfaatkan `DocumentFragment` dan koordinasi `requestAnimationFrame`.