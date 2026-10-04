# BAB 08: Quiz, Challenge, & Knowledge Check
**Bab 08: Heaps, Priority Queues, dan Algoritma Seleksi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Representasi Implisit Pohon Biner Lengkap (*Implicit Array Representation*)**  
   Mengapa *Binary Heap* hampir selalu diimplementasikan di atas struktur data *contiguously allocated array* daripada menggunakan simpul berbasis *pointer* (*linked nodes*)? Jelaskan formulasi indeks anak kiri, anak kanan, dan induk pada array berbasis 0 (*zero-indexed*), serta buktikan bagaimana relasi topologi ini menjamin properti *complete binary tree* tanpa fragmentasi memori.

2. **Analisis Matematis Bound Kompleksitas `build_heap` vs Sekuensial `insert`**  
   Membangun sebuah *Binary Heap* dari array acak berukuran $N$ menggunakan algoritma Floyd (*bottom-up heapify*) memiliki kompleksitas waktu $\mathcal{O}(N)$, sedangkan menyisipkan elemen satu per satu via `insert` membutuhkan $\mathcal{O}(N \log N)$. Tuliskan derivasi formal berbasis deret geometri konvergensi:
   $$\sum_{h=0}^{\lfloor\log_2 N\rfloor} \frac{h}{2^h} = 2$$
   dan jelaskan mengapa perbedaan batas atas node pada kedalaman $h$ menyebabkan perbedaan asimptotik yang signifikan ini.

3. **Invarian Min-Heap vs Max-Heap dan Ketidakstabilan (*Instability*) Relatif**  
   Jelaskan secara formal invarian struktural dan parsial yang harus dipenuhi oleh *Max-Heap*. Mengapa algoritma pengurutan *Heap Sort* secara inheren bersifat *unstable*? Berikan contoh urutan array minimal yang membuktikan terjadinya pelanggaran stabilitas posisi relatif elemen-elemen dengan kunci (*keys*) yang identik.

4. **D-ary Heap: Trade-off Branching Factor terhadap Hardware Performance**  
   Dalam implementasi *d-ary heap* (di mana setiap simpul memiliki maksimal $d$ anak, dengan $d > 2$):  
   - Bagaimana penurunan kedalaman pohon ($\log_d N$) memengaruhi kompleksitas `sift-up` vs `sift-down`?  
   - Mengapa nilai $d=4$ atau $d=8$ sering kali berkinerja lebih cepat daripada $d=2$ pada CPU modern, meskipun jumlah komparasi per tingkat pada operasi `sift-down` meningkat sebesar $\mathcal{O}(d)$?

5. **Prinsip Dual-Heap untuk Median Maintenance**  
   Jelaskan mekanisme partisi data kontinu menggunakan dua heap: satu *Max-Heap* untuk paruh bawah (*lower half*) dan satu *Min-Heap* untuk paruh atas (*upper half*). Apa kondisi invarian ukuran (*size balance*) dan nilai (*value ordering*) yang harus dijaga agar pengambilan nilai median tetap beroperasi dalam waktu instan $\mathcal{O}(1)$?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Debugging Heap Invariant Corruption akibat In-Place Mutation**  
   Diberikan struktur data Min-Heap yang menyimpan referensi objek `Task { id: int, priority: int }`. Setelah sistem berjalan beberapa jam, fungsi `extract_min()` mulai mengembalikan tugas yang prioritasnya lebih rendah daripada elemen lain di heap.  
   - Analisis root-cause dari anomali ini jika diketahui ada thread eksternal yang memutasi field `task.priority` secara langsung.  
   - Bagaimana mendesain API heap yang kebal terhadap mutasi eksternal tanpa harus menduplikasi objek (*defensive copy*) secara berlebihan?

2. **Arsitektur Indexed Priority Queue (IPQ) untuk Efisiensi `decrease-key`**  
   Operasi `decrease-key` standar pada Binary Heap memerlukan pencarian linier $\mathcal{O}(N)$ untuk menemukan posisi elemen sebelum dilakukan `sift-up`.  
   - Rancang struktur pemetaan dua arah (*bidirectional lookup*: array `keys`, array `heap`, dan array `inverse_heap`/`pm`) yang memungkinkan mutasi nilai dan re-balancing berjalan dalam $\mathcal{O}(\log N)$.  
   - Tunjukkan bagaimana operasi pertukaran elemen (`swap`) di internal heap harus mengabstraksi pembaruan indeks inversi tersebut agar pointer state tidak mengalami sinkronisasi parsial (*desynchronization*).

3. **Mitigasi Cache Miss pada Bottom Layers Heap Traversal**  
   Pada heap dengan ratusan juta elemen ($N > 10^8$), operasi `sift-down` mengalami degradasi performa drastis akibat kegagalan *L1/L2 cache hit*.  
   - Jelaskan mengapa traversal dari akar (*root*) menuju daun (*leaf*) menghasilkan pola akses memori non-sekuensial dengan lonjakan *stride* eksponensial ($2i+1$).  
   - Jelaskan bagaimana teknik *B-Heap Layout* atau *Cache-Oblivious Array Layout* memitigasi bottleneck *hardware cache-line* ini dibandingkan *array-based heap* standar.

4. **Handling Pathological Case pada Dynamic Array Resizing**  
   Sebuah priority queue menggunakan *resizable array* (vektor dinamis) di backend. Pada beban kerja real-time dengan variasi throughput tinggi, terjadi lonjakan latensi (*latency spike*) periodik p99.9 saat `push` dieksekusi.  
   - Diagnosis bagaimana interaksi antara alokasi memori sistem operasi, pemanggilan `memcpy`, dan fragmentasi heap berkontribusi pada latensi p99.9 tersebut.  
   - Usulkan arsitektur alokasi memori (misalnya *chunked array* atau *ring-buffer based buckets*) untuk mencapai alokasi *zero-copy* deterministik.

5. **Penanganan Kasus Ekstrem: Sift-Down dengan Duplikasi Kunci Masif**  
   Jika sebuah *Min-Heap* diisi dengan 90% elemen bernilai prioritas sama, operasi `extract_min` berulang dapat memicu *branch misprediction* berat pada saat menentukan anak terkecil antara $2i+1$ dan $2i+2$.  
   - Analisis assembly logic dari branching perbandingan anak:
     ```c
     int child = (heap[right] < heap[left]) ? right : left;
     ```
   - Bagaimana cara menulis kode `sift-down` tanpa percabangan bersyarat (*branchless programming*) untuk meminimalkan penalti *pipeline flush* pada arsitektur modern x86-64/ARM64?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Streaming Ingestion Engine (1M Events/Sec)
Sebuah sistem agregasi metrik IoT menerima 1.000.000 metrik per detik via Apache Kafka. Kebutuhan bisnis adalah mempertahankan jendela geser (*sliding window*) untuk mendapatkan "Top-100 Perangkat dengan Konsumsi Daya Tertinggi". Implementasi saat ini menggunakan satu buah Max-Priority Queue global yang dilindungi oleh sebuah `Mutex`. Profiling produksi menunjukkan utilisasi CPU mencapai 100% dengan kondisi *thread lock contention* masif, dan latency ingestion meleset dari batas SLA (< 50ms).
- **Pertanyaan Diagnostik:**
  1. Mengapa penggunaan Max-Heap unbounded menghasilkan kompleksitas komputasi yang tidak optimal untuk skenario pencarian Top-K konstan, dan mengapa pendekatan Min-Heap berukuran tetap ($K=100$) secara radikal memangkas latensi?
  2. Rancang arsitektur konkurensi nir-kunci (*lock-free*) atau *partition-based aggregation* menggunakan thread-local heaps dan periodic merge untuk mengeliminasi bottleneck sinkronisasi antar-thread.

### Skenario B: Race Condition dan Priority Inversion pada Job Dispatcher
Sebuah platform komputasi awan menggunakan *shared memory Indexed Min-Heap* untuk mendistribusikan micro-tasks ke ratusan worker processes. Fitur baru ditambahkan: "Cancel Task" dan "Reprioritize Task" yang mengeksekusi `delete(taskId)` dan `decrease_key(taskId, new_priority)`. Di bawah beban konkurensi tinggi, sistem mengalami *race condition* di mana indeks internal heap menunjuk ke slot yang salah, mengakibatkan pembatalan tugas yang tidak bersalah (*wrong task execution*) atau panic *index out of bounds*.
- **Pertanyaan Diagnostik:**
  1. Identifikasi *atomic boundary* yang gagal dipertahankan jika pembaruan struktur heap dan tabel pemetaan indeks id-ke-posisi tidak berada dalam sebuah operasi primitif atomik sinkron.
  2. Bagaimana merancang skema locking *fine-grained* atau mekanisme *read-copy-update* (RCU) / sequence locks untuk memastikan integritas struktural internal heap tanpa mengorbankan performa *throughput* pembacaan (*dispatch*) oleh worker?

### Skenario C: Arsitektur Scheduler Latensi Sangat Rendah (Timer Engine)
Sistem gateway perdagangan frekuensi tinggi (HFT) harus mengelola 5.000.000 order timeouts (TTL bervariasi dari 1ms hingga 60 detik). Arsitektur lama menggunakan Min-Heap standar untuk melacak order mana yang kadaluwarsa lebih dulu. Namun, insertion rate yang mencapai 200.000 order/detik menghasilkan overhead $\mathcal{O}(\log N)$ yang menghabiskan budget siklus CPU perdagangan.
- **Pertanyaan Diagnostik:**
  1. Lakukan trade-off analysis mendalam antara penggunaan *Hierarchical Hashed Timing Wheels* (Varghese & Lauck approach) vs *Cache-Aligned 4-ary Min-Heap* dalam konteks:
     - Kompleksitas waktu amortisasi operasi `schedule_timer`, `cancel_timer`, dan `tick`.
     - Footprint memori dan *cache spatial locality*.
  2. Pada ambang batas dispersi waktu (*variance of TTL*) seperti apa struktur Min-Heap tetap lebih unggul dibandingkan Timing Wheel?

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance Bounded Sliding-Window Top-K Streaming Filter**

### Problem Statement
Anda ditugaskan membangun komponen mesin agregasi log streaming performa tinggi (*low-latency, zero-allocation*). Komponen ini harus menerima aliran data string metrik dengan skor keparahan secara konstan, lalu mempertahankan peringkat Top-K elemen teratas secara real-time. Jika elemen yang sudah ada di Top-K menerima pembaruan skor (*event update*), skornya harus disinkronkan tanpa menduplikasi data atau merusak struktur ranking.

### Requirements
1. **Core Data Structure:** Implementasikan *Indexed Bounded Min-Heap* dari nol (dilarang menggunakan modul built-in seperti `heapq` Python, `std::priority_queue` C++, atau `java.util.PriorityQueue`).
2. **Operations Supported:**
   - `void observe(string element_id, double score)`: Jika heap belum penuh ($< K$), masukkan elemen. Jika sudah penuh dan `score > min_score`, ganti elemen terkecil atau perbarui elemen yang sudah ada jika ID-nya cocok, lalu rebalance heap.
   - `vector<pair<string, double>> get_top_k()`: Mengembalikan snapshot terurut dari $K$ elemen teratas dalam urutan descending ($\mathcal{O}(K \log K)$).
3. **Complexity Guarantees:**
   - Pencarian elemen berdasarkan ID: $\mathcal{O}(1)$.
   - Operasi `observe()` untuk pembaruan skor atau penyisipan: amortized $\mathcal{O}(\log K)$.
   - Ruang memori: Tepat $\mathcal{O}(K)$, tidak boleh tumbuh proporsional terhadap total elemen stream yang diamati ($N$).

### Constraints
- $K$ terikat secara statis pada inisialisasi: $10 \le K \le 100.000$.
- Stream input: Hingga $10^7$ pemanggilan `observe()`.
- **Zero-Allocation Rule:** Tidak boleh ada alokasi heap dinamis baru (`malloc`, `new`) yang terjadi di dalam hot-path method `observe()`. Seluruh buffer memori (array heap dan array hash table/slot map) harus di-prealokasikan di muka saat konstruksi objek.

### Expected Output & Format
Sediakan implementasi menggunakan bahasa pemrograman yang mendukung kontrol memori/referensi ketat (C++17/20, Rust, Go, atau Java tingkat lanjut dengan preallocated arrays). 

Kode harus memuat:
1. Definisi struct/class lengkap untuk `IndexedBoundedHeap`.
2. Mekanisme pelacakan posisi heap via lookup table (menggunakan hash-table preallocated atau open-addressing static hashtable).
3. Test suite benchmarking sederhana yang mendemonstrasikan $10^6$ operasi berjalan di bawah 500 milidetik pada CPU standar modern.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batas asimptotik matematis dari algoritma Floyd's `build_heap` ($\mathcal{O}(N)$) dan mengapa sequential `sift-up` bernilai $\mathcal{O}(N \log N)$.
- [ ] Mekanisme pemetaan heap ke array berbasis 0 (`left = 2i + 1`, `right = 2i + 2`, `parent = (i - 1) / 2`).
- [ ] Dampak arsitektural pemilihan branching factor $d$ (*d-ary heap*) terhadap utilisasi *CPU cache lines* vs komparasi branching.
- [ ] Alasan fundamental mengapa *Heap Sort* tidak stabil (*unstable*) dan bagaimana menyuntikkan *tie-breaker index* untuk memaksakan stabilitas.
- [ ] Dinamika struktur *Indexed Priority Queue* menggunakan tabel inversi posisional untuk mendukung operasi `decrease-key` / `delete(id)` dalam waktu $\mathcal{O}(\log N)$.
- [ ] Pola partisi Dual-Heap (Max-Heap + Min-Heap) untuk mempertahankan median dinamis dalam waktu baca $\mathcal{O}(1)$ dan mutasi $\mathcal{O}(\log N)$.

### Saya tidak perlu menghafal:
- [ ] Penurunan matematis penuh deret hipergeometrik di luar pemahaman bahwa simpul terbanyak berada di level terbawah dengan jarak penelusuran minimum.
- [ ] Implementasi internal algoritma *Fibonacci Heap* atau *Brodal Queue* yang rumit, cukup pahami batas teoretisnya ($\mathcal{O}(1)$ amortized `decrease-key`) dan trade-off mengapa struktur tersebut jarang diimplementasikan di industri karena faktor konstanta memori yang masif.
- [ ] Nilai eksak floating-point konversi rasio median secara manual.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan algoritma dasar `sift-up` dan `sift-down` dari nol tanpa bug rekursi (berbasis iterasi presisi).
- [ ] Merancang struktur data *Top-K Streaming Filter* yang mengeliminasi pembengkakan memori dengan memanfaatkan *bounded Min-Heap* berukuran tetap.
- [ ] Melakukan troubleshooting dan profiling konkurensi pada aplikasi terdistribusi yang melibatkan contention pada antrean prioritas bersama (*shared priority queues*).
- [ ] Mencegah terjadinya *heap invariant violation* akibat mutasi objek referensi yang tersimpan di dalam antrean prioritas.
- [ ] Menulis logika `sift-down` yang ramah terhadap prediksi percabangan instruksi mesin (*branchless or branch-predictor friendly*).