# BAB 06: Quiz, Challenge, & Knowledge Check
**Inti Bahasa JavaScript (ECMAScript Modern): Eksekusi & Data**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Execution Context Lifecycle (Creation vs. Execution Phase)**  
   Jelaskan secara mendalam apa yang terjadi pada memori ketika JavaScript Engine menginisialisasi *Global Execution Context* (GEC) atau *Function Execution Context* (FEC). Bedakan fase *Creation* (pembentukan *Lexical Environment*, *Variable Environment*, dan registrasi *Environment Record*) dengan fase *Execution* terhadap alokasi variabel `var`, deklarasi `function`, serta `let` dan `const`.

2. **Primitive vs. Reference Types di Stack dan Heap Memory**  
   Bagaimana V8 (atau engine JavaScript modern lainnya) membagi penyimpanan data antara *Call Stack* dan *Memory Heap*? Jelaskan mengapa manipulasi properti pada objek yang di-*assign* ke variabel baru menyebabkan mutasi pada objek referensi asli, sedangkan re-assignment pada tipe primitif bersifat terisolasi secara mutlak.

3. **Temporal Dead Zone (TDZ) & Hoisting Mechanics**  
   Secara spesifikasi ECMAScript, apakah deklarasi `let` dan `const` mengalami *hoisting*? Jelaskan definisi formal dari *Temporal Dead Zone* (TDZ), di mana batas awal dan akhir dari TDZ dalam sebuah blok kode, serta mengapa engine melempar `ReferenceError` alih-alih mengevaluasinya menjadi `undefined`.

4. **Abstract Equality vs. Strict Equality Engine Algorithm**  
   Berdasarkan spesifikasi ECMAScript *Type Conversion / Abstract Equality Comparison Algorithm*, bedah langkah demi langkah mengapa ekspresi `[] == ![]` mengevaluasi ke `true`, sedangkan `[] === ![]` mengevaluasi ke `false`. Sebutkan peran operasi internal `ToBoolean` dan `ToPrimitive` dalam proses evaluasi tersebut.

5. **Lexical Scope dan Static Outer Environment Reference**  
   Jelaskan mengapa *scope* dalam JavaScript disebut bersifat *Lexical* (atau *Static*). Bagaimana engine menentukan resolusi pengenal variabel (*Identifier Resolution*) menaiki *Scope Chain* melalui referensi *Outer Environment*, dan mengapa posisi fisik pemanggilan fungsi (*Call Site*) sama sekali tidak memengaruhi rantai pencarian *scope* tersebut?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Call Stack Starvation: Synchronous Recursion vs. Microtask Queue Loop**  
   Bandingkan dampak struktural terhadap *Call Stack* dan UI thread responsiveness antara rekursi sinkron murni (`function recurse() { recurse(); }`) dengan loop tak terbatas melalui *microtask* (`function loop() { queueMicrotask(loop); }`). Mengapa salah satu kasus memicu `RangeError: Maximum call stack size exceeded` sementara kasus lainnya membekukan (*freeze*) browser tab tanpa memicu *Stack Overflow*?

2. **Closure Lifecycle & Memory Retention Mechanics**  
   Bagaimana sebuah *Closure* mempertahankan referensi ke *Lexical Environment* induknya setelah *Execution Context* fungsi induk tersebut selesai dieksekusi dan di-*pop* dari *Call Stack*? Dalam kondisi seperti apa *closure* yang menangkap variabel besar di *parent scope* dapat menimbulkan *accidental memory leak* secara senyap?

3. **Object Immutability Traps & Structural Degradation**  
   Bandingkan perilaku dan keandalan proteksi data antara `const`, `Object.preventExtensions()`, `Object.seal()`, dan `Object.freeze()`. Mengapa `Object.freeze()` secara bawaan bersifat *shallow*, dan apa konsekuensi komputasi/performa (*runtime overhead*) jika seorang engineer menerapkan *deep freeze* rekursif pada struktur data bersarang (*nested data*) yang sangat besar?

4. **Garbage Collection: Cyclic References vs. Mark-and-Sweep**  
   Jelaskan mengapa algoritma *Reference Counting* pada engine generasi awal gagal menangani kasus *Cyclic Reference* (dua objek yang saling mereferensikan satu sama lain tanpa ada akses dari global root), dan bagaimana algoritma *Mark-and-Sweep* modern menyelesaikan masalah ini menggunakan prinsip *Reachability*.

5. **Property Descriptors & Object Masking**  
   Apa implikasi dari modifikasi atribut *Property Descriptor* (`value`, `writable`, `enumerable`, `configurable`) menggunakan `Object.defineProperty()`? Bagaimana cara memanfaatkan deskriptor ini dan tipe data `Symbol` untuk membuat properti metadata yang tidak dapat ditimpa (*non-writable*), tidak terhapus (*non-configurable*), dan tidak bocor saat dieksekusi oleh `for...in` loop maupun `Object.keys()`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Production Outage akibat Memory Leak pada Single-Page Application (SPA)
Sebuah dashboard analitik real-time berbasis SPA mengalami degradasi performa drastis setelah dibuka selama lebih dari 45 menit. Penggunaan memori tab browser melonjak dari 60 MB hingga melampaui 1.8 GB, berujung pada tab browser crash (`Aw, Snap! - Error code: Out of Memory`). 
Arsitektur kode menggunakan pola pub/sub global di mana setiap kali user berpindah halaman (komponen di-mount dan di-unmount), komponen tersebut memanggil:
```javascript
eventBus.subscribe('TELEMETRY_UPDATE', (payload) => {
  this.processData(payload, largeHistoricalCacheArray);
});
```
* **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat bagaimana interaksi antara *Closure*, *Event Registration*, dan *Garbage Collection Reachability Root* menyebabkan seluruh array `largeHistoricalCacheArray` gagal dibebaskan dari *Heap Memory* meskipun komponen UI telah dihancurkan.
  2. Bagaimana metodologi Anda menggunakan Chrome DevTools (Heap Snapshot, Allocation Instrumentation on Timeline) untuk membuktikan retention path dari kebocoran memori ini?
  3. Tuliskan refaktorisasi kode yang menjamin pemutusan siklus referensi (*deterministic cleanup*) saat siklus hidup komponen berakhir.

---

### Skenario B: Data Inconsistency & Mutation Leak pada State Management Transaksi
Pada modul checkout sebuah platform e-commerce, user melaporkan insiden di mana total diskon kupon yang diterapkan pada cart pesanan pertama secara acak "merembes" (*polluting*) ke transaksi user lain pada sesi aplikasi lokal yang sama. Modul kalkulasi harga diimplementasikan sebagai berikut:
```javascript
const defaultPricingConfig = {
  currency: 'IDR',
  taxRate: 0.11,
  discounts: { voucher: 0, seasonal: 0 },
  metadata: { appliedAt: null }
};

function calculateOrderTotal(cart, customConfig = defaultPricingConfig) {
  const config = Object.assign({}, customConfig);
  if (cart.voucherCode) {
    config.discounts.voucher = 25000;
    config.metadata.appliedAt = new Date().toISOString();
  }
  // Kalkulasi total biaya...
  return computeFinalPrice(cart.items, config);
}
```
* **Pertanyaan Diagnostik:**
  1. Bedah mengapa penggunaan `Object.assign({}, customConfig)` gagal melindungi integritas state data transaksi global. Apa yang terjadi pada level memori (*Heap Pointer*) terhadap properti `discounts` dan `metadata`?
  2. Mengapa insiden ini tidak terdeteksi saat unit test dijalankan secara terisolasi, namun langsung meledak saat aplikasi berjalan di lingkungan produksi dengan eksekusi transaksi yang simultan/berurutan?
  3. Bagaimana solusi implementasi penjaminan *state immutability* yang efisien tanpa menggunakan library eksternal berukuran besar (seperti Immutable.js)?

---

### Skenario C: Bottleneck Performa GC Pause pada Data Feed Stream Berkecepatan Tinggi
Sistem monitoring IoT menerima 5.000 data point per detik melalui WebSocket. Setiap frame data diparsing sebagai JavaScript Object baru, dimutasi, dan diteruskan ke kanvas grafik. Setiap 3–5 detik, terjadi frame-drop parah (*jank*) selama 80–120ms di layar user. Profiling DevTools menunjukkan bahwa *main thread* terhenti akibat aktivitas *Major Garbage Collection* (GC Sweep/Compacting).
* **Pertanyaan Diagnostik:**
  1. Mengapa alokasi objek JSON sementara (*short-lived objects*) dalam frekuensi sangat tinggi memicu tekanan ekstrem (*allocation churn*) pada V8 *New Generation Space (Nursery)*?
  2. Analisis trade-off performa antara mempertahankan struktur objek dinamis (standard JS objects) vs mengadopsi *Object Pooling* atau beralih ke *TypedArray* / *ArrayBuffer* terstruktur untuk representasi data stream ini.
  3. Bagaimana restrukturisasi penanganan data dapat menurunkan beban GC hingga mendekati zero-allocation pada loop eksekusi utama?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Engine "Isolated Scope Store" dengan Structural Immutability Guard & Rollback
**Problem Statement:**  
Sebagai Principal Engineer, Anda diminta membangun modul inti manajemen state lokal bernama `ScopeStore` yang bertugas mengeksekusi mutasi data bisnis secara ketat. Modul ini harus kebal terhadap mutasi tidak disengaja (*accidental side-effects*), mencegah kebocoran referensi antar context, dan mendukung rollback otomatis jika mutasi gagal di tengah jalan.

**Requirements:**
1. **Instantiation & Encapsulation:**
   * `ScopeStore` diinisialisasi dengan sebuah `initialState` (berupa nested object).
   * State internal **hanya** boleh diakses melalui method `.getState()`.
   * Akses luar via `.getState()` tidak boleh memberikan referensi langsung ke state internal (tidak boleh bisa dimutasi secara eksternal).
2. **Transactional Mutations:**
   * Store menyediakan method `.commit(transactionFn)`.
   * `transactionFn` menerima *draft* state. Jika `transactionFn` melempar *exception* (error), state internal harus tetap berada pada kondisi sebelum transaksi dimulai (*atomic rollback*).
   * Jika sukses, snapshot state diperbarui secara deterministik.
3. **Immutability Enforcement:**
   * Setiap snapshot state yang dihasilkan harus bersifat *Deep Frozen* (rekursif) secara runtime untuk memvalidasi bahwa modul eksternal yang memegang referensi lama tidak dapat mengubahnya.
4. **Leak-Proof Event Subscriptions:**
   * Sediakan method `.subscribe(listenerFn)`.
   * Method ini harus mengembalikan fungsi `unsubscribe()` murni.
   * `ScopeStore` harus mendeteksi dan mencegah *circular reference subscription leaks* menggunakan `WeakSet` atau mekanisme tracking referensi internal.
5. **Zero External Dependencies:**
   * Wajib diimplementasikan murni menggunakan JavaScript ECMAScript Modern (ES2022+). Dilarang mengimpor library pihak ketiga (Lodash, Immer, Redux, dll.).

**Constraints:**
* Tangani potensi terjadinya *Prototype Pollution* (validasi keys seperti `__proto__`, `constructor`, `prototype`).
* Kode harus bersih, berstandar industri, terisolasi dalam *closure* atau *private class fields* (`#`), dan dilengkapi validasi tipe data defensif.

**Expected Output:**
Sebuah berkas JavaScript modular (`ScopeStore.js`) yang mengekspor class `ScopeStore`, disertai script pengujian minimal (assertions) yang mendemonstrasikan:
1. Kegagalan mutasi langsung dari luar (state tidak berubah saat properti nested diotak-atik).
2. Mekanisme *atomic rollback* ketika callback di dalam `.commit()` melemparkan error di tengah proses mutasi.
3. Unsubscribe listener yang membersihkan referensi fungsi listener secara deterministik dari memory store.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup *Execution Context* (Creation Phase vs. Execution Phase) dan bagaimana memori dialokasikan sebelum kode dieksekusi baris-per-baris.
- [ ] Perbedaan representasi Stack Memory (pointer & nilai primitif) dan Heap Memory (alokasi memori dinamis untuk objek struktural).
- [ ] Konsep formal *Temporal Dead Zone* (TDZ) serta perbedaan perlakuan Engine terhadap `var`, `let`, `const`, dan `function declaration`.
- [ ] Cara kerja *Scope Chain* melalui referensi internal `[[OuterEnv]]` secara leksikal, bukan dinamis.
- [ ] Perilaku dasar Garbage Collector (Mark-and-Sweep) dan kondisi spesifik yang mempertahankan *Reachability Root* sehingga memicu memory leak.
- [ ] Algoritma kesetaraan JavaScript (`==` vs `===`), serta urutan pemanggilan operasi konversi internal (`ToPrimitive`, `valueOf`, `toString`).

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel konversi koersi tipe data anomali / *esoteric edge cases* (misal: `[] + {}` vs `{}` + `[]`). Cukup pahami aturan mendasar konversi: `ToPrimitive` selalu diutamakan pada operasi matematika/kesetaraan abstrak.
- [ ] Ukuran spesifik byte alokasi Call Stack pada masing-masing vendor browser (misal: batasan persis maksimum frame stack V8 vs SpiderMonkey). Cukup pahami bahwa batasan tersebut finite dan mudah terlampaui oleh rekursi tak terkontrol.
- [ ] Detail algoritma internal implementasi low-level garbage collector V8 (*Scavenger semi-space copying*, *Orinoco parallel marking*). Cukup kuasai konsep *Generational Hypothesis* dan cara mendeteksi retensi memori tak terpakai via Profiler.

### Saya harus bisa melakukan:
- [ ] Melakukan analisis dan visualisasi urutan Call Stack saat terjadi eksekusi kode sinkron, asinkron, dan nested callbacks.
- [ ] Menemukan dan menambal kebocoran memori (*memory leak*) pada aplikasi frontend menggunakan Chrome DevTools Heap Profiler (Snapshot diffing & Allocation timeline).
- [ ] Mengimplementasikan deep copy / deep clone yang aman secara runtime menggunakan native web/JS API (`structuredClone`) dan memahami batasannya (ketidakmampuan meng-clone fungsi).
- [ ] Menerapkan pattern *Object Immutability* defensif pada level enterprise untuk menjaga integritas data arsitektur aplikasi tanpa degradasi performa yang signifikan.
- [ ] Menggunakan Property Descriptors (`Object.defineProperty`) untuk mengontrol visibilitas, mutabilitas, dan konfigurabilitas objek secara presisi.