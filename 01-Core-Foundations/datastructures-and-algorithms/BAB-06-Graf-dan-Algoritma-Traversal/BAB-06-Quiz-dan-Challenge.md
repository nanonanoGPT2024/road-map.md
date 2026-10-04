# BAB 06: Quiz, Challenge, & Knowledge Check
**Bab 06: Tabel Hash, Fungsi Hash, dan Resolusi Kolisi (Hash Tables & Collision Resolution)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Trade-off Fungsi Hash: Kriptografis vs Non-Kriptografis**
   Jelaskan perbedaan mendasar antara fungsi hash kriptografis (misal: SHA-256) dan fungsi hash non-kriptografis berkinerja tinggi (misal: MurmurHash3, xxHash, SipHash) dalam konteks implementasi Tabel Hash. Mengapa runtime modern (seperti Rust, Python, Go) secara *default* memilih SipHash alih-alih algoritma yang secara komputasi lebih cepat seperti xxHash?

2. **Mekanisme Kontrak Kesetaraan (*Equality and Hash Contract*)**
   Hampir setiap bahasa pemrograman modern memberlakukan kontrak ketat antara operasi kesetaraan (*equality*, misal `equals()`) dan pembuatan nilai hash (misal `hashCode()`). Analisis secara presisi apa konsekuensi deterministik dan struktural pada Tabel Hash jika:
   - Dua objek menghasilkan nilai hash yang sama tetapi bernilai `equals() == false`.
   - Dua objek bernilai `equals() == true` tetapi menghasilkan nilai hash yang berbeda.

3. **Separate Chaining vs Open Addressing: Aspek CPU Cache Locality**
   Bandingkan arsitektur *Separate Chaining* (menggunakan linked list atau red-black tree per bucket) dan *Open Addressing* (menggunakan array flat dengan linear/quadratic probing). Mengapa pada arsitektur CPU kontemporer, *Open Addressing* sering kali secara signifikan mengungguli *Separate Chaining* dalam operasi baca (*read throughput*), meskipun probabilitas kolisi cluster-nya secara teoritis lebih tinggi?

4. **Amortized Analysis pada Dynamic Resizing dan Load Factor**
   Definisikan *Load Factor* ($\alpha = \frac{n}{m}$). Jelaskan pembuktian matematis secara intuitif mengapa operasi *insert* pada Tabel Hash bernilai *amortized* $O(1)$ meskipun terdapat operasi ekspansi tabel berbiaya $O(n)$. Mengapa nilai ambang batas $\alpha \approx 0.7 - 0.75$ secara universal dipilih sebagai batas pelatuk (*trigger*) ekspansi pada skema *linear probing*?

5. **Anatomi Penghapusan (*Deletion*) pada Open Addressing: Kebutuhan Tombstone**
   Pada skema *Open Addressing* dengan *Linear Probing*, mengapa elemen yang dihapus tidak boleh langsung diinisialisasi ulang menjadi penanda kosong primitif (misal: `null` atau `0`)? Jelaskan mekanisme *Tombstone* (penanda *deleted*) dan bagaimana pengaruhnya terhadap integritas operasi pencarian (*search probe chain*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Primary Clustering dan Secondary Clustering**
   Uraikan fenomena *Primary Clustering* pada *Linear Probing* dan *Secondary Clustering* pada *Quadratic Probing*. Bagaimana formulasi matematis dari *Double Hashing* ($h(k, i) = (h_1(k) + i \cdot h_2(k)) \pmod m$) mampu memitigasi kedua fenomena tersebut, dan syarat mutlak apa yang harus dipenuhi oleh fungsi $h_2(k)$ terhadap ukuran tabel $m$?

2. **Degradasi Kinerja Akibat Penumpukan Tombstone (*Tombstone Accumulation*)**
   Sebuah sistem cache internal berbasis *Linear Probing* mengalami degradasi latensi pembacaan drastis ($p99$ melonjak hingga $O(n)$) setelah beroperasi selama 48 jam, meskipun metrik utilisasi memori menunjukkan *Load Factor* aktif hanya berada di angka $0.35$. Diagnosis akar masalahnya berdasarkan siklus hidup *tombstone* dan rancang strategi mitigasi (*re-hashing in place* atau *backshift deletion*).

3. **Arsitektur Internal SIMD Probing: Paradigma Swiss Table**
   Jelaskan inovasi arsitektural di balik *Swiss Table* (diadopsi oleh Google Abseil dan Rust `std::collections::HashMap`). Bagaimana pemisahan array metadata 1-byte (*control bytes*) dari array data payload, yang dipadukan dengan instruksi SIMD, mampu mengubah kompleksitas pencarian probing dari sekuensial individual menjadi inspeksi multi-slot secara paralel?

4. **Transisi Struktur Resolusi Kolisi Dinamis (*Treeification*)**
   Pada implementasi Java 8+ `HashMap`, bucket *Separate Chaining* akan bertransformasi dari *Singly Linked List* menjadi *Red-Black Tree* saat ukuran linked list melampaui ambang batas tertentu (`TREEIFY_THRESHOLD = 8`). Analisis trade-off memori dan komputasi di balik keputusan desain ini. Mengapa pohon tersebut harus didegradasi kembali menjadi linked list (*untreeify*) saat ukuran menyusut di bawah ambang batas tertentu?

5. **Stop-the-World Latency pada Resizing Skala Gigabyte**
   Jika sebuah Tabel Hash menampung 50 juta entri dan membutuhkan alokasi memori berukuran gigabytes, operasi resizing konvensional akan memblokir thread aplikasi (*latency spike* parah). Rancang mekanisme *Incremental Resizing* (seperti yang diimplementasikan pada Redis `dict`) yang memungkinkan migrasi entri dilakukan secara bertahap tanpa degradasi ketersediaan sistem.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Produksi Akibat Hash Collision DoS (HashDoS)
Sebuah layanan API Gateway publik yang memproses payload JSON berukuran besar mengalami lonjakan utilisasi CPU hingga 100% pada semua instance worker-nya saat menerima volume request yang relatif normal. Tim SRE menemukan bahwa latensi parsing JSON melonjak dari 2ms menjadi 1800ms per request. Setelah membedah heap dump, ditemukan bahwa jutaan kunci payload JSON dari request eksternal menghasilkan nilai hash 32-bit yang identik pada parser internal berbasis hash table.
* **Pertanyaan Diagnostik:**
  1. Jelaskan bagaimana penyerang secara deterministik dapat mengeksploitasi fungsi hash yang tidak memiliki *randomized seed* untuk memaksa hash table jatuh ke performa *worst-case* $O(n^2)$.
  2. Langkah mitigasi arsitektural darurat apa yang harus diterapkan pada parser JSON dan hash table runtime untuk melumpuhkan serangan ini secara tuntas?

### Skenario B: Race Condition dan Infinite Loop pada Skema Concurrent Rehashing
Sebuah tim mengimplementasikan in-memory key-value store kustom menggunakan *Separate Chaining* yang diakses secara paralel oleh puluhan thread pembaca dan penulis tanpa sinkronisasi yang memadai (*unsynchronized concurrent access*). Dalam beban tinggi, beberapa worker thread tiba-tiba mengalami *infinite loop* (100% CPU usage) di dalam method `get()`, yang tidak pernah kembali (*hang* permanen).
* **Pertanyaan Diagnostik:**
  1. Rekonstruksi bagaimana operasi `resize()`/`transfer()` yang dieksekusi secara konkuren oleh dua thread tanpa penguncian dapat membalikkan penunjuk pointer linked list dan membentuk siklus tertutup (*circular reference / loop*) pada list bucket.
  2. Evaluasi desain konkurensi modern (misal: *Lock Striping* vs *CAS-based Bucket Level Locking* seperti pada Java `ConcurrentHashMap`) untuk mengeliminasi anomali ini tanpa mengorbankan skalabilitas konkurensi.

### Skenario C: Trade-off Arsitektur Cache Low-Latency: Robin Hood Hashing vs Cuckoo Hashing
Anda bertindak sebagai Principal Engineer yang merancang L1 Network Cache untuk sistem *High-Frequency Trading* (HFT). Persyaratan non-fungsional sistem menetapkan bahwa operasi baca (*lookup*) harus memiliki latensi deterministik dengan batas atas (*worst-case bound*) yang sangat ketat, alokasi memori nol (*zero allocation* pada runtime), dan tidak ada toleransi terhadap lonjakan latensi akibat *chain traversal*.
* **Pertanyaan Diagnostik:**
  1. Bandingkan karakteristik teoritis dan praktis antara *Robin Hood Hashing* (dengan prinsip *rich-steal-from-the-poor*) dan *Cuckoo Hashing* (dengan multi-hash functions dan *worst-case constant lookup* $O(1)$) untuk kebutuhan sistem tersebut.
  2. Berikan rekomendasi arsitektur final Anda dengan mengevaluasi trade-off antara biaya operasi penulisan (*insertion cascade/eviction loop*), utilisasi memori maksimum, dan stabilitas latensi pembacaan pada persentil $p99.99$.

---

## 4. Chapter Challenge

**Tantangan Praktis: Implementasi High-Performance Key-Value Store dengan Robin Hood Hashing dan Backshift Deletion**

### Deskripsi Masalah
Sebagai insinyur sistem, Anda diminta mengimplementasikan struktur data *In-Memory Key-Value Table* berbasis *Open Addressing* dari nol (tanpa pustaka hash bawaan/standar map bawaan bahasa pemrograman). Tabel ini dirancang untuk membaca data secara instan pada sistem deterministik dengan meminimalkan varians dari *Probe Sequence Length* (PSL).

### Requirements
1. **Struktur Data Core:**
   - Implementasikan tabel menggunakan array berurutan kontinu (*flat array*) untuk memaksimalkan *cache locality*.
   - Setiap slot harus menyimpan: `Key`, `Value`, status slot (EMPTY, OCCUPIED), dan nilai integer `PSL` (*Probe Sequence Length* yang mencatat jarak elemen dari posisi *ideal hash slot*-nya).
2. **Operasi Penyisipan (Robin Hood Invariant):**
   - Saat menyisipkan elemen baru: Jika terjadi kolisi dan elemen yang akan disisipkan memiliki PSL yang *lebih besar* daripada elemen yang saat ini menempati slot tersebut, lakukan *swap* (curi slot tersebut).
   - Lanjutkan probing untuk elemen yang terusir (*evicted element*) dengan nilai PSL yang telah dinaikkan secara berjenjang hingga menemukan slot kosong.
3. **Operasi Penghapusan (*Backshift Deletion*):**
   - **DILARANG** menggunakan penanda *Tombstone*.
   - Saat elemen pada indeks $i$ dihapus, geser elemen berikutnya pada indeks $(i + 1)$ mundur ke indeks $i$ HANYA JIKA elemen tersebut memiliki PSL $> 0$.
   - Kurangi nilai PSL elemen yang digeser sebesar 1. Ulangi proses ini ke slot-slot selanjutnya hingga menemukan slot kosong atau elemen dengan PSL $= 0$.
4. **Fungsi Hash & Sizing:**
   - Gunakan fungsi hash non-kriptografis 64-bit yang cepat (implementasikan minimal FNV-1a atau versi ringkas dari MurmurHash).
   - Ukuran tabel harus merupakan bilangan pangkat dua ($2^k$), gunakan teknik bitwise masking (`hash & (capacity - 1)`) sebagai pengganti operasi modulo (`%`).
5. **Ambang Batas & Resize:**
   - Terapkan mekanisme auto-resize (kapasitas dikalikan 2) saat *Load Factor* mencapai ambang batas $\alpha \ge 0.85$.

### Constraints
- Dilarang keras menggunakan tipe data Map/Dictionary bawaan bahasa (misal: `java.util.Map`, `std::unordered_map`, Go `map`, Python `dict`).
- Zero Dynamic Memory Allocation selama siklus operasi `get()` dan `delete()`. Seluruh memori dialokasikan di muka (*pre-allocated*) saat inisialisasi tabel atau saat fase resizing.
- Kompleksitas waktu untuk `get()` pada *worst-case* harus memiliki varians PSL yang sangat rendah (mendekati seragam).

### Expected Output & Validasi
- Sediakan benchmark driver yang melakukan:
  1. Penyisipan 100.000 elemen unik berpasangan string/integer.
  2. Menampilkan statistik metrik operasional:
     - Rata-rata PSL (*Average PSL*).
     - PSL Maksimum (*Max PSL*).
     - Utilisasi memori sebelum dan sesudah 50.000 penghapusan acak via *Backshift Deletion*.
  3. Verifikasi integritas: Seluruh sisa 50.000 elemen harus tetap dapat ditemukan secara valid (`assert(get(key) == expected_value)`), dan tidak ada kebocoran memori atau loop pencarian tak berujung.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mengapa fungsi hash dalam Tabel Hash harus mendistribusikan kunci secara seragam (*uniform distribution*) dan deterministik di seluruh ruang alamat bucket.
- [ ] Perbedaan fundamental antara *Separate Chaining*, *Linear Probing*, *Quadratic Probing*, *Double Hashing*, *Robin Hood Hashing*, dan *Cuckoo Hashing*.
- [ ] Dampak *CPU cache miss* pada linked-list traversal (*Separate Chaining*) dibandingkan dengan *spatial locality* dari array contiguous (*Open Addressing*).
- [ ] Efek cascading dari *Tombstone* pada *Linear Probing* dan bagaimana hal itu merusak batas pencarian hingga memicu degradasi dari $O(1)$ ke $O(n)$.
- [ ] Konsekuensi operasional dari *Load Factor* ($\alpha$) terhadap trade-off ruang memori (*memory footprint*) versus latensi akses.
- [ ] Potensi vektor serangan DoS berbasis algoritma (*HashDoS*) dan cara mengamankannya menggunakan fungsi hash berkunci (*keyed hash*) dengan *randomized seeds* seperti SipHash.
- [ ] Mekanisme internal struktur data generasi lanjut seperti *Swiss Table* (SIMD group probing) dan *Incremental Rehashing*.

### Saya tidak perlu menghafal:
- [ ] Konstanta numerik eksak dari algoritma MurmurHash3, xxHash, atau SipHash (cukup pahami prinsip dispersi bit dan avalanche effect-nya).
- [ ] Nilai prima spesifik yang digunakan dalam *Double Hashing* modulo tables (cukup pahami bahwa modulus harus relatif prima terhadap step size).
- [ ] Sintaks mikro kode SIMD assembly spesifik (seperti SSE2, AVX-512) yang digunakan oleh *Swiss Table* (cukup pahami abstraksi kontrol byte dan paralelisasi pencariannya).

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *Linear Probing* dan *Separate Chaining* secara mandiri tanpa menggunakan pustaka standar bahasa.
- [ ] Mendiagnosis dan memperbaiki *infinite loop* atau memori leak pada tabel hash kustom akibat bug penanganan *Tombstone* atau mutasi kunci (*key mutation*).
- [ ] Mengukur dan menganalisis metrik internal tabel hash: distribusi slot, kolisi rata-rata, panjang probe maksimal, dan rata-rata probe chain.
- [ ] Mengonfigurasi dan menyetel parameter kapasitas awal (*initial capacity*) dan load factor tabel hash enterprise untuk meminimalkan alokasi ulang (*re-allocations*) pada jalur kritis sistem.
- [ ] Mengimplementasikan strategi mitigasi penghapusan tanpa tombstone (*Backshift Deletion*) untuk mempertahankan performa optimal probing array flat.