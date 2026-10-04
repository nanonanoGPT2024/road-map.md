# BAB 02: Quiz, Challenge, & Knowledge Check
**Two Pointers & Sliding Window Mechanics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Prasyarat Monotonisitas (Monotonicity Invariant)**
   Mengapa properti monotonisitas (*monotonicity*) merupakan syarat mutlak agar algoritma *Two Pointers* konvergen ke kompleksitas waktu $O(N)$ tanpa memerlukan *backtracking*? Jelaskan secara matematis apa yang terjadi pada *search space* ketika elemen array tidak terurut atau fungsi evaluasi jendela (*window evaluation function*) kehilangan sifat monotoniknya.

2. **Mekanika Amortisasi Kompleksitas Waktu**
   Dalam pola *Dynamic Sliding Window*, kode implementasi sering kali melibatkan struktur *nested loop* (sebuah loop `while` di dalam loop `for`/`while`). Buktikan secara formal mengapa kompleksitas waktu keseluruhan dari algoritma tersebut tetap terikat secara ketat pada $O(N)$ (*amortized time complexity*), bukan $O(N^2)$. Tinjau dari batas eksekusi pergeseran *left pointer* dan *right pointer*.

3. **Analisis Konvergensi Floyd’s Cycle Detection (Tortoise and Hare)**
   Pada algoritma *Fast & Slow Pointer* untuk deteksi siklus (Floyd’s Cycle-Finding Algorithm), buktikan mengapa rasio kecepatan $2x$ dan $1x$ menjamin deteksi siklus dalam batas $O(\mu + \lambda)$ (di mana $\mu$ adalah jarak ke awal siklus dan $\lambda$ adalah panjang siklus). Mengapa penggunaan kecepatan $3x$ atau $4x$ justru dapat menyebabkan inefisiensi atau memperlambat konvergensi pada siklus berukuran tertentu?

4. **In-Place Array Compaction & Memory Safety**
   Pada pola *Two Pointers: Read/Write Pointer* (misal: *Remove Duplicates*, *Move Zeroes*, *In-place Partitioning*), jelaskan bagaimana relasi invarian $W \le R$ (indeks *Write* selalu lebih kecil atau sama dengan indeks *Read*) menjamin integritas data elemen yang belum diproses tanpa memerlukan alokasi memori tambahan $O(N)$. Apa implikasi pola akses ini terhadap *CPU Cache Locality*?

5. **Dilema Subarray Sum: Sliding Window vs. Prefix Sum**
   Diberikan masalah pencarian *subarray* yang memiliki jumlah total sama dengan target $K$. Jelaskan secara fundamental mengapa teknik *Sliding Window* dapat menyelesaikan masalah ini dalam $O(N)$ jika semua elemen adalah bilangan bulat positif ($\ge 0$), namun **gagal total** jika array mengandung bilangan negatif, sehingga mengharuskan transisi ke pola *Prefix Sum + Hash Map*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Troubleshooting Off-By-One pada Interval Window State**
   Perhatikan implementasi *Longest Substring Without Repeating Characters* berikut:
   ```cpp
   int lengthOfLongestSubstring(string s) {
       vector<int> lastIndex(256, -1);
       int maxLen = 0, left = 0;
       for (int right = 0; right < s.length(); right++) {
           if (lastIndex[s[right]] != -1) {
               left = lastIndex[s[right]] + 1; // POTENSI BUG
           }
           lastIndex[s[right]] = right;
           maxLen = max(maxLen, right - left + 1);
       }
       return maxLen;
   }
   ```
   Tunjukkan *test case* minimal di mana kode di atas menghasilkan kalkulasi yang salah (*incorrect window contract*). Jelaskan akar masalahnya (*root cause*) dan berikan koreksi satu baris untuk menjaga *left pointer* tetap monotonik maju.

2. **Dampak Memory Footprint: Direct-Address Table vs Hash Map**
   Pada *Sliding Window* yang melacak frekuensi karakter (seperti pada *Minimum Window Substring*), jelaskan perbandingan performa mekanistik tingkat rendah antara menggunakan `std::unordered_map<char, int>` (atau `HashMap<Character, Integer>` di Java) versus fixed-size array `int freq[128]` atau `int freq[256]`. Tinjau dari aspek:
   - Alokasi memori heap vs stack
   - *Pointer dereferencing* dan *cache misses*
   - Overhead operasi komparasi kevalidan window state

3. **Mekanika Monotonic Deque pada Sliding Window Maximum**
   Dalam *Sliding Window Maximum* ($k$ ukuran window), algoritma optimal menggunakan *Monotonic Deque* untuk mencapai $O(N)$. 
   - Jelaskan operasi internal yang menjaga invariant elemen di dalam deque selalu *strictly decreasing*.
   - Mengapa elemen yang lebih kecil dari elemen baru yang masuk harus di-*evict* dari belakang deque (*pop_back*) secara permanen? Apakah ada skenario di mana elemen tersebut masih bisa menjadi maksimum di masa depan?

4. **Transisi Kontraksi Jendela: Exact Length vs Optimization Search**
   Bandingkan arsitektur algoritma *Sliding Window* dengan:
   - **Fixed-size window**: Pergeseran simultan ($L++$ dan $R++$ secara serentak setelah ukuran window tercapai).
   - **Variable-size minimum window** (misal: *Minimum Size Subarray Sum*): Ekspansi agresif $R$, diikuti kontraksi agresif $L$.
   - Tentukan bagaimana strategi pembaruan variabel global (`minLen` atau `maxLen`) ditempatkan: apakah di dalam loop kontraksi atau di luar loop kontraksi? Jelaskan dampak logisnya jika salah menempatkan pembaruan tersebut.

5. **Bidirectional Two Pointers pada Unsorted vs Sorted Sequences**
   Banyak insinyur berasumsi bahwa pola dua pointer dari dua ujung (*Left* di 0, *Right* di $N-1$) hanya berlaku pada array yang terurut (misal: *Two Sum II*). Namun, pada masalah *Trapping Rain Water* dan *Container With Most Water*, pola ini bekerja pada array yang **tidak terurut**.
   - Analisis secara matematis mengapa properti eliminasi *search space* tetap valid pada kedua masalah tersebut tanpa memerlukan pengurutan array terlebih dahulu.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike pada Real-Time Telemetry Sliding Window Rate Limiter
Sebuah API Gateway memproses 500.000 *request* per detik (RPS). Tim arsitektur mengimplementasikan algoritma *Sliding Window Log* di dalam memori menggunakan struktur data *Doubly Linked List* (atau queue) untuk membatasi kuota tiap pengguna maksimal 1.000 *request* per menit. Pada kondisi trafik puncak, sistem mengalami lonjakan latensi P99 hingga 2.500 ms dan memicu lonjakan penggunaan memori (OOM).

**Pertanyaan Diagnostik:**
1. Mengapa struktur data *Sliding Window Log* berbasis *timestamp tracking* mengalami degradasi memori dan CPU yang signifikan pada skenario *burst traffic*?
2. Bagaimana Anda mendesain ulang algoritma tersebut menggunakan pendekatan kombinasi *Sliding Window Counter* atau memori-terikat (*fixed bucket circular array*) untuk membatasi kompleksitas memori menjadi $O(1)$ per pengguna sembari mempertahankan akurasi batas kuota?

### Skenario B: Desinkronisasi Thread-Safety pada Sliding Window Ring Buffer
Sebuah aplikasi sistem perdagangan frekuensi tinggi (*High-Frequency Trading*) menggunakan struktur data *Circular Ring Buffer* berbasis *Two Pointers* (`head` dan `tail`) tanpa *mutex* (*lock-free*) untuk mentransfer data paket harga pasar dari *Network Consumer Thread* (penulis) ke *Order Execution Thread* (pembaca). Dalam pengujian beban tinggi, terjadi insiden di mana pembaca membaca data korup atau pointer saling melompati (*overrun/underrun*).

**Pertanyaan Diagnostik:**
1. Identifikasi bagaimana *CPU instruction reordering* dan ketiadaan *memory barrier/atomic acquire-release semantics* pada pembaruan `head` dan `tail` dapat merusak invariant *circular two-pointer*.
2. Bagaimana Anda menstrukturkan operasi pembaruan pointer dan status window (*full/empty check*) agar thread-safe tanpa menggunakan kunci berat (*heavy lock*)?

### Skenario C: Trade-off Arsitektur Streaming: Tumbling vs Sliding Window pada Aggregation Engine
Platform analisis data log terdistribusi (seperti Apache Flink atau custom Kafka Streams processor) harus menghitung metrik agregasi anomali jaringan setiap 10 detik dengan rentang pantauan 1 jam (*1-hour window sliding every 10 seconds*). 
Terdapat dua pilihan arsitektur:
- **Pendekatan Murni Sliding Window:** Menyimpan seluruh *event granular* selama 1 jam terakhir dan menggeser window setiap 10 detik.
- **Pendekatan Micro-Tumbling Window (Bucketed Accumulator):** Menghitung pra-agregasi dalam *bucket* ukuran 10 detik, lalu menerapkan *Two Pointers* atau *Sliding Window* pada deret hasil pra-agregasi tersebut.

**Pertanyaan Diagnostik:**
1. Lakukan analisis kuantitatif terhadap perbedaan *memory footprint* dan konsumsi *network I/O* antara kedua pendekatan tersebut jika volume data masuk adalah 10.000 event/detik.
2. Jelaskan kompromi (*trade-off*) apa yang harus dikorbankan (misal: penanganan *late-arriving data*, presisi statistik non-aditif seperti *percentile/median*) ketika memilih pendekatan *Micro-Tumbling Bucket*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Network Packet Jitter Buffer & Out-of-Order Assembler

#### Problem Description
Dalam protokol transmisi media real-time berbasis UDP (seperti WebRTC atau VoIP), paket-paket data audio/video sering tiba di sisi klien dalam kondisi:
1. Tidak berurutan (*out-of-order*).
2. Terdapat duplikasi paket (*duplicate packets*).
3. Mengalami *jitter* waktu tiba (*variable latency*).

Tugas Anda adalah merancang komponen inti: **Jitter Buffer Packet Assembler** menggunakan arsitektur **Sliding Window Berukuran Dinamis** berbasis array siklik (*Circular Buffer*). Komponen ini harus menerima aliran paket data yang masuk secara acak dan merekonstruksinya menjadi aliran sekuensial kontinu yang siap dibaca oleh dekoder media.

#### Requirements
1. **Window State Mechanics:**
   - Pertahankan jendela dengan batas sekuens $[Sequence_{base}, Sequence_{base} + WindowSize - 1]$.
   - $Sequence_{base}$ adalah nomor sekuens berikutnya yang diharapkan oleh dekoder.
   - Paket dengan $Sequence < Sequence_{base}$ dianggap kedaluwarsa/duplikat dan harus langsung di-*discard* ($O(1)$).
   - Paket dengan $Sequence \ge Sequence_{base} + WindowSize$ berada di luar jangkauan jendela dan harus memicu strategi penanganan buffer overflow.
2. **Sequential Ejection (Contraction):**
   - Sediakan metode `emitReadyPackets()` yang mengembalikan semua paket berurutan yang telah lengkap mulai dari $Sequence_{base}$, sambil menggeser $Sequence_{base}$ ke depan (*window contraction*).
3. **Loss Concealment Trigger:**
   - Jika paket hilang (*missing sequence*) dan telah tertahan melebihi batas ambang toleransi waktu ($T_{drop}$), sistem harus memotong (*drop*) paket yang hilang tersebut, memajukan $Sequence_{base}$, dan melanjutkan pembacaan paket berikutnya agar pemutaran media tidak terhenti (*audio freeze*).
4. **Efficiency:**
   - Semua operasi penyisipan paket (`pushPacket`) dan pembuangan paket kedaluwarsa harus memiliki kompleksitas waktu $O(1)$.
   - Alokasi memori buffer harus menggunakan fixed-size memory pool yang dapat digunakan kembali (*zero dynamic memory allocation* di jalur eksekusi utama).

#### Constraints
- Nomor sekuens paket berupa unsigned 16-bit integer ($0 \le Sequence \le 65535$), yang berarti Anda harus menangani masalah **Integer Wrap-Around** (misal: paket $65535$ diikuti oleh paket $0$).
- Ukuran maksimum jendela (*Max Window Size*): $1024$ paket.
- Kompleksitas Waktu: $O(1)$ amortized per paket yang masuk dan keluar.
- Kompleksitas Memori Tambahan: Maksimal $O(WindowSize)$, dilarang menggunakan heap allocation (`new`/`malloc`) saat pemrosesan *runtime*.

#### Expected Output
Sajikan rancangan arsitektur data, penanganan modulo/wrap-around sekuens, serta implementasi fungsi utama (minimal pseudocode presisi tinggi atau kode C++/Java/Go/Rust) yang mendemonstrasikan:
1. Logika penentuan indeks circular buffer berdasarkan nomor sekuens.
2. Penanganan transisi sekuens saat terjadi wrap-around (misal perbedaan jarak antara sekuens $65534$ dan $2$).
3. Prosedur kontraksi dan emisi paket kontinu.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Logika pembuktian mengapa algoritma *Two Pointers* dan *Sliding Window* menjamin kompleksitas waktu $O(N)$ melalui teknik amortisasi pergerakan batas indeks.
- [ ] Prasyarat *monotonic property* pada struktur data dan bagaimana menentukan apakah suatu masalah dapat diselesaikan dengan jendela geser atau memerlukan struktur bantuan (*auxiliary data structures*).
- [ ] Mekanisme deteksi siklus Floyd (kecepatan $2x$ vs $1x$), titik temu (*meeting point*), serta pembuktian matematika penemuan titik awal siklus (*cycle origin*).
- [ ] Perbedaan fundamental antara *fixed-size window*, *dynamically expanding window*, dan *shrinkable window based on constraint satisfaction*.
- [ ] Pemanfaatan *Monotonic Deque* dalam mempertahankan nilai ekstrem (minimum/maksimum) di dalam jendela geser secara $O(1)$ per operasi.
- [ ] Mengapa *Sliding Window* tidak dapat bekerja langsung pada masalah subarray dengan bilangan bulat negatif dan mengapa kombinasi *Prefix Sum + Hash Map* menjadi substitusi yang tepat.
- [ ] Dampak *CPU cache hierarchy* dan *memory layout* terhadap kecepatan eksekusi kode *Two Pointers* pada in-place array partitioning.

### Saya tidak perlu menghafal:
- [ ] Pola kode sintaksis spesifik bahasa pemrograman untuk struktur array atau list.
- [ ] Nomor-nomor soal LeetCode tertentu yang menggunakan label *Sliding Window*.
- [ ] Trik atau *micro-optimization* berbasis kompilator yang tidak relevan dengan arsitektur algoritma secara teoretis maupun praktis.
- [ ] Formula absolut ukuran window konstan untuk setiap masalah jaringan atau stream, karena nilai tersebut selalu bergantung pada karakteristik *throughput* dan *delay* spesifik sistem.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi masalah komputasi yang memiliki karakteristik reduksi ruang pencarian (*search space pruning*) menggunakan *Two Pointers*.
- [ ] Mengimplementasikan algoritma *dynamic sliding window* tanpa menyebabkan *infinite loop* atau *off-by-one errors* pada saat kontraksi indeks.
- [ ] Memilih struktur data pelacak status jendela (*window state tracker*) yang optimal (misal: array frekuensi berukuran statis vs tabel *hash*) untuk menghindari overhead runtime di sistem skala masif.
- [ ] Menangani *edge cases* kritis: array kosong, array dengan elemen seragam, array tanpa jawaban valid, ukuran window lebih besar dari array, dan integer wrap-around.
- [ ] Merancang algoritma berbasis *Sliding Window* untuk data stream real-time dengan batas penggunaan memori strictly $O(1)$ atau $O(K)$.