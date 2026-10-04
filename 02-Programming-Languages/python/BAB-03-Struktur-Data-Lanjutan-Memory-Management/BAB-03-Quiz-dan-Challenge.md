# BAB 03: Quiz, Challenge, & Knowledge Check
**Struktur Data Lanjutan & Memory Management**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **CPython Reference Counting vs. Generational Garbage Collector**
   CPython mengadopsi mekanisme *hybrid* untuk manajemen memori: *Reference Counting* sebagai garis pertahanan utama dan *Generational Garbage Collector* (GC) sebagai pendamping. Jelaskan secara mekanistik mengapa *reference counting* deterministik saja tidak mampu menangani masalah *cyclic references* (referensi melingkar), serta jelaskan bagaimana Generational GC mengabstraksi objek ke dalam tiga generasi (Gen 0, Gen 1, Gen 2) menggunakan konsep *heuristic collection threshold*.

2. **Dampak Mekanikal `__slots__` terhadap Memory Layout Objek**
   Secara *default*, instansiasi kelas Python menyertakan atribut `__dict__` bertipe kamus dinamis untuk menyimpan atribut *instance*. Bagaimana deklarasi `__slots__` secara internal merestrukturisasi alokasi memori objek di level C struct (`PyObject`), bagaimana mekanismenya meniadakan *overhead* `__dict__` dan `__weakref__`, serta apa konsekuensi arsitekturalnya terhadap pewarisan (*inheritance*) dan dynamic attribute assignment?

3. **Hierarki Internal CPython Memory Allocator (PyMalloc)**
   Jelaskan hierarki alokasi memori CPython mulai dari *System Heap* OS, *Arenas* (256 KB), *Pools* (4 KB), hingga *Blocks* (kelipatan 8 hingga 512 bytes). Mengapa CPython mengimplementasikan allocator khususnya sendiri (PyMalloc) untuk alokasi objek kecil ($\le 512$ bytes) ketimbang mendelegasikannya secara langsung ke fungsi `malloc()` standar glibc/OS?

4. **Karakteristik Kompleksitas dan Desain Alokasi: `collections.deque` vs. `list`**
   Bandingkan representasi struktur data `list` (berbasis *dynamic array contiguous memory*) dengan `collections.deque` (berbasis *doubly-linked block list*). Mengapa operasi *prepend* (`insert(0, item)` / `pop(0)`) pada `list` bernilai $\mathcal{O}(N)$ sedangkan pada `deque` bernilai $\mathcal{O}(1)$? Analisis pula *trade-off* pemanfaatan CPU cache-locality dan *overhead* memori per pointer saat melakukan random indexing $\mathcal{O}(1)$ vs $\mathcal{O}(N)$.

5. **Arsitektur Compact Dict (Python 3.6+)**
   Sejak implementasi PyPy diadopsi oleh CPython 3.6+, struktur internal `dict` didesain ulang menjadi *Compact Dict*. Jelaskan arsitektur pemisahan array `indices` (hash table sparse) dan array `entries` (dense sequential array). Bagaimana arsitektur ini memangkas konsumsi memori hingga 20–25% sekaligus menjamin sifat *insertion-ordered traversal* secara deterministik?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **String & Integer Interning Hazards**
   CPython menerapkan optimasi *interning* otomatis pada small integers ($-5$ hingga $256$) dan string literal yang menyerupai identifier. Uraikan mengapa memverifikasi identitas data dinamis menggunakan operator `is` alih-alih `==` merupakan cacat logika fatal (*anti-pattern*) pada arsitektur produksi, khususnya saat runtime memuat input dari network socket, proses parsing JSON, atau kompilasi bytecode terpisah.

2. **Diagnostik Cyclic Reference pasca PEP 442**
   Sebelum Python 3.4 (PEP 442), keberadaan metode `__del__` pada objek yang terlibat dalam siklus referensi membuat objek tersebut dikategorikan sebagai *uncollectable* dan tersangkut di `gc.garbage`. Jelaskan bagaimana PEP 442 mengubah *finalization order* pada siklus referensi. Bagaimanakah Anda mendeteksi objek yang gagal di-deallokasi menggunakan kombinasi modul `gc` (`gc.set_debug(gc.DEBUG_UNCOLLECTABLE)`) dan visualisasi referensi via library eksternal `objgraph`?

3. **Weak Reference Callbacks dan Pencegahan Memory Leak pada Caching**
   Mengapa penggunaan `weakref.ref` atau `weakref.WeakValueDictionary` menjadi solusi mutlak dalam implementasi *in-memory cache* untuk objek berumur panjang? Jelaskan siklus hidup (*lifecycle*) objek ketika satu-satunya referensi yang tersisa adalah *weak reference*, dan bagaimana callback yang didaftarkan pada `weakref.finalize` dieksekusi secara aman tanpa menghalangi *deallocation sequence*.

4. **Heap Profiling Menggunakan `tracemalloc` vs. OS RSS Metric**
   Sebuah *worker process* Python menunjukkan peningkatan metrik Resident Set Size (RSS) pada sistem operasi dari 200 MB menjadi 1.5 GB, namun `gc.collect()` mengembalikan angka 0 objek yang dibebaskan. Bagaimana Anda menggunakan modul `tracemalloc` untuk membandingkan dua *snapshot* alokasi memory block (`tracemalloc.Filter`, `Compare_to`), dan bagaimana Anda menganalisis fenomena *memory fragmentation* di mana memori CPython tidak dikembalikan ke OS meskipun objek telah dihancurkan?

5. **In-place Mutation & Hash Invalidation pada Custom Objects**
   Sebuah objek dari kelas kustom diimplementasikan dengan metode `__hash__` dan `__eq__` yang bergantung pada nilai atribut yang bersifat *mutable*. Jelaskan bahaya yang timbul saat objek tersebut dijadikan *key* dalam `dict` atau elemen dalam `set`, lalu atribut tersebut dimutasi di kemudian waktu. Apa yang terjadi secara internal di dalam hash table bucket lookup, dan bagaimana mekanisme ini menyebabkan *virtual memory leak* (data hilang tetapi tetap berada di memori)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Incident Memory Leak pada Data Pipeline Skala Besar
Sebuah microservice berbasis Python (FastAPI/Celery) memproses data telemetri IoT sebesar 20 juta payload per jam. Setiap payload diparsing ke dalam bentuk *domain model object* sebelum ditulis ke database. Setelah beroperasi terus menerus selama 4 jam, worker pod Celery mengalami penghentian paksa oleh kernel Linux (*OOMKilled*, Exit Code 137). Profiling awal menunjukkan:
* Metrik `len(gc.get_objects())` melonjak tajam secara linear seiring bertambahnya request.
* Garbage Collector Generasi 2 berjalan normal tetapi tidak membebaskan ruang memori yang signifikan.
* Tim developer menduga terdapat kebocoran pada fungsi transformator data yang menggunakan lambda closure dan penanganan logging error yang menyimpan referensi ke `sys.exc_info()`.

**Pertanyaan Diagnostik:**
1. Bagaimana cara Anda memverifikasi secara empiris apakah frame traceback dari `sys.exc_info()` atau exception chaining (`except Exception as e`) menahan referensi sirkular ke local variable stack frame?
2. Langkah mitigasi arsitektur apa yang harus diambil untuk payload DTO: migrasi ke `__slots__`, *namedtuple*, primitive dictionary, atau `@dataclass(slots=True)`? Hitung estimasi efisiensi memori teoritis dari langkah tersebut.

---

### Skenario B: Race Condition dan Mutasi Data pada Asynchronous Local Cache
Sebuah platform e-commerce menggunakan cache lokal di dalam proses berbasis `collections.defaultdict(list)` untuk mengagregasi pesanan inventaris sementara sebelum batch-write ke database PostgreSQL. Operasi dilakukan di dalam event loop `asyncio` dengan konkurensi tinggi (5.000 coroutine bersamaan).
Secara intermiten, sistem mengalami degradasi performa di mana CPU mencapai 100%, query lookup cache menghasilkan data pesanan milik pengguna lain (*data leakage*), dan sesekali memunculkan error fatal: `RuntimeError: dictionary changed size during iteration`.

**Pertanyaan Diagnostik:**
1. Mengapa `dict` CPython, meskipun aman dari segi *thread-safety* untuk operasi atomik tunggal di bawah proteksi GIL, tetap rentan terhadap korupsi data logis dan `RuntimeError` pada arsitektur non-preemptive concurrency (`asyncio`) ketika melibatkan iterasi dan mutasi?
2. Rancang struktur data terisolasi yang *race-condition-free* menggunakan primitif sinkronisasi atau struktur data immutable (*structural sharing*) untuk menggantikan `defaultdict` tersebut tanpa mengorbankan throughput I/O non-blocking.

---

### Skenario C: Trade-off Arsitektur Sistem Order Matching Engine
Anda adalah Lead Architect yang diminta merancang modul *In-Memory Priority Matching Engine* untuk sistem trading derivatif. Sistem harus memproses aliran pesan transaksi (*buy/sell limit orders*) dengan karakteristik:
* Pemasukan order baru (*push*) harus memiliki latensi rendah ($\le \mathcal{O}(\log N)$).
* Eksekusi order dengan harga prioritas terbaik (*peek/pop*) harus instan ($\mathcal{O}(1)$ atau $\mathcal{O}(\log N)$).
* Pembatalan order (*arbitrary cancellation*) dari tengah antrean berdasarkan `order_id` harus didukung tanpa memicu *full table scan* ($\mathcal{O}(N)$).

Tim Anda memperdebatkan tiga kandidat:
1. `heapq` bawaan Python.
2. Kombinasi `dict` terurut (Python 3.7+) dengan `bisect`.
3. Struktur data kustom *Balanced BST* (misalnya Red-Black Tree atau AVL) yang diikat via C-extension/Cython.

**Pertanyaan Diagnostik:**
1. Mengapa modul `heapq` bawaan Python gagal memenuhi kebutuhan *arbitrary cancellation* secara efisien, dan bagaimana teknik *lazy deletion* (tombstoning) menggunakan `dict` lookup dapat mengatasi batasan ini tanpa merusak invarian binary heap?
2. Buat matriks evaluasi teknis yang memperbandingkan trade-off kompleksitas waktu, kompleksitas ruang, dan cache-locality dari ketiga opsi di atas untuk skenario kapasitas 5 juta antrean order aktif!

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Leak LRU Cache Engine dengan Tombstoning & Memory-Bounded Eviction

#### Problem Statement
Anda ditugaskan mengimplementasikan komponen inti *In-Memory Cache Engine* berkinerja tinggi yang ditujukan untuk sistem microservice mission-critical. Komponen bawaan seperti `functools.lru_cache` tidak dapat digunakan karena tidak mendukung *memory-footprint hard ceiling* (hanya mendukung pembatasan berdasarkan jumlah elemen `maxsize`, bukan kuota byte memori), tidak mendukung TTL (*Time-To-Live*) terdistribusi, serta rentan terhadap *reference retention* yang menyebabkan memori sulit diklaim kembali oleh sistem.

#### Requirements
1. **Struktur Data Hibrida**: Bangun struktur data `BoundedLRUCache` tanpa menggunakan `functools.lru_cache` atau `collections.OrderedDict`. Anda wajib mengimplementasikan struktur data manual menggunakan kombinasi *Hash Map* (`dict`) dan *Doubly Linked List* internal.
2. **Memory Footprint Optimization**:
   * Setiap *node* antrean harus didefinisikan menggunakan kelas dengan proteksi `__slots__` ketat guna mengeliminasi overhead `__dict__`.
   * Cache harus dibatasi oleh kuota memori fisik total dalam satuan Bytes (misal: `max_memory_bytes=50_000_000` / 50MB).
   * Pengukuran ukuran objek cache harus menghitung jejak memori riil secara rekursif (deep size) menggunakan mekanisme kustom atau `sys.getsizeof`.
3. **Lazy Expiration with Tombstoning**:
   * Setiap entri memiliki parameter TTL.
   * Implementasikan strategi *dual-eviction*: jika kapasitas memori terlampaui, lakukan eviksi LRU; jika entri diakses dalam kondisi kedaluwarsa, lakukan *tombstoning/unlinking* seketika secara $\mathcal{O}(1)$.
4. **Leak Prevention**: Gunakan modul `weakref` pada referensi callback atau metadata listener untuk memastikan cache tidak menahan objek yang seharusnya telah di-deallokasi oleh pemanggil di luar engine cache.

#### Constraints
* **Pure Python Standard Library**: Modul pihak ketiga (seperti `psutil`, `pympler`) dilarang di dalam kode implementasi engine cache utama (hanya diizinkan modul: `sys`, `time`, `gc`, `weakref`, `tracemalloc`).
* Operasi `get()`, `put()`, dan `delete()` harus berjalan pada amortized time complexity $\mathcal{O}(1)$.
* Zero Circular Reference: Instansiasi cache engine yang dibuat dan dihancurkan berulang kali tidak boleh meninggalkan objek di Generasi 2 GC.

#### Expected Output
1. File skrip Python modular (`bounded_cache.py`) yang mengimplementasikan kelas `Node`, `DoublyLinkedList`, dan `BoundedLRUCache`.
2. Blok testing integrasi mandiri di dalam blok `if __name__ == '__main__':` yang mendemonstrasikan:
   * **Benchmarking Memory**: Menggunakan `tracemalloc` untuk mencatat alokasi sebelum dan sesudah 500.000 operasi `put()`, membuktikan ukuran memori terdistribusi secara konstan di bawah ambang batas (contoh batas: 15 MB).
   * **Verifikasi Eviction**: Log pembuktian bahwa node terlama diev月のi dengan benar saat kuota byte memori habis.
   * **Garbage Collection Test**: Eksekusi `gc.collect()` menghasilkan 0 referensi tertahan saat cache instance dibuang dari context execution.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara *Reference Counting* (deterministik, instan) dan *Generational Tracing GC* (asinkron, heuristik) di CPython.
- [ ] Anatomi PyMalloc: Bagaimana *Arenas*, *Pools*, dan *Blocks* beroperasi menangani alokasi memori $\le 512$ bytes untuk mencegah fragmentasi heap OS.
- [ ] Struktur internal implementasi Python `dict` modern (Compact Dict: pemisahan sparse index table dan dense key-value array).
- [ ] Mekanisme kerja `__slots__` dalam mengubah layout C struct objek, meniadakan dynamic `__dict__`, serta dampaknya terhadap penggunaan memori.
- [ ] Keterbatasan modul `heapq` dan mengapa penghapusan elemen arbitrer memerlukan teknik *tombstoning* atau *lazy eviction*.
- [ ] Peran dan cara kerja modul `weakref` (`ref`, `WeakValueDictionary`, `finalize`) dalam memutus siklus referensi pada cache.
- [ ] Konsep *Memory Fragmentation* pada level OS: mengapa process memory RSS tidak langsung turun meskipun data di dalam Python telah dihapus via `del` dan `gc.collect()`.

### Saya tidak perlu menghafal:
- [ ] Formula matematis eksak algoritma komputasi probing hash table CPython (`perturb = (perturb >> 5) + 1`).
- [ ] Nilai bitmask hexadecimal internal flag object header CPython (`PyObject_HEAD` macros).
- [ ] Alamat memori absolut atau offset biner spesifik dari pointer low-level C struct pada implementasi runtime tertentu.

### Saya harus bisa melakukan:
- [ ] Menganalisis dan mendeteksi sumber kebocoran memori pada level aplikasi menggunakan modul `tracemalloc` dan visualisasi `objgraph`.
- [ ] Mengoptimalkan kelas data Python menggunakan `@dataclass(slots=True)` atau `__slots__` manual untuk menghemat ruang memori hingga 40-60%.
- [ ] Mengonfigurasi threshold Generational GC (`gc.set_threshold()`) atau menonaktifkannya sementara (`gc.disable()`) untuk skenario komputasi batch throughput tinggi yang sensitif terhadap latency pause.
- [ ] Memilih dan mengimplementasikan struktur data performa tinggi yang tepat (`deque`, `bisect`, `heapq`, `dict`) sesuai dengan profil kompleksitas waktu operasi ($\mathcal{O}(1)$ vs $\mathcal{O}(\log N)$ vs $\mathcal{O}(N)$).
- [ ] Mengidentifikasi dan membongkar *circular reference* yang disebabkan oleh lambda closure, penanganan frame exception, atau callback functions.