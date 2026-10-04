# BAB 04: Quiz, Challenge, & Knowledge Check
**Binary Search & Divide and Conquer**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Invarian Loop dan Terminasi**  
   Jelaskan secara matematis dan logis bagaimana pendefinisian batas pencarian (search space boundaries) `[left, right]` (inklusif) vs `[left, right)` (inklusif-eksklusif) memengaruhi terminasi loop (`while (left <= right)` vs `while (left < right)`) serta mutasi pointer (`right = mid - 1` vs `right = mid`). Apa konsekuensi terhadap stabilitas algoritma jika terjadi ketidakkonsistenan antara kondisi terminasi dan mutasi pointer?

2. **Mitigasi Aritmetika Integer Overflow**  
   Rumus klasik pencarian titik tengah adalah `mid = (left + right) / 2`. Jelaskan secara mendalam skenario arsitektur memori di mana ekspresi ini menyebabkan *silent arithmetic overflow* pada tipe data *signed 32-bit integer* di level representasi biner. Bandingkan efisiensi dan keamanan mesin antara alternatif `left + (right - left) / 2` dan bitwise operation `(left + right) >>> 1`.

3. **Master Theorem dan Analisis Rekursi Divide and Conquer**  
   Diberikan relasi rekurensi $T(n) = aT(n/b) + f(n)$ dengan $a \ge 1$ dan $b > 1$. Jelaskan tiga kasus utama dalam Master Theorem berdasarkan perbandingan asimtotik antara $f(n)$ dan $n^{\log_b a}$. Terapkan analisis ini pada algoritma Merge Sort dan jelaskan mengapa dekomposisi Divide and Conquer pada algoritma tersebut menghasilkan kompleksitas waktu optimal $O(n \log n)$ namun membutuhkan penalti kompleksitas ruang $O(n)$.

4. **Sifat Monotonik (Monotonicity) dan Ruang Solusi**  
   Binary Search sering kali direduksi secara keliru hanya sebagai algoritma pencarian pada array terurut. Buktikan secara konseptual mengapa sifat *monotonicity* (fungsi predikat Boolean $f(x) \to \{0, 1\}$ yang mempertahankan sifat non-decreasing atau non-increasing) merupakan syarat perlu dan cukup (necessary and sufficient condition) untuk mengimplementasikan Binary Search pada *discrete solution space*.

5. **Dekomposisi Masalah: Divide and Conquer vs Dynamic Programming**  
   Keduanya sama-sama memecah masalah menjadi sub-masalah yang lebih kecil. Apa parameter fundamental yang membedakan domain permasalahan yang harus diselesaikan menggunakan pendekatan Divide and Conquer murni (seperti Quick Sort, Fast Fourier Transform) dibandingkan dengan Dynamic Programming? Jelaskan implikasinya terhadap *call stack overhead* dan pemanfaatan *overlapping subproblems*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Debugging Infinite Loop pada Left/Right Biased Midpoint**  
   Perhatikan potongan kode untuk mencari elemen terakhir yang memenuhi kondisi tertentu:
   ```cpp
   while (left < right) {
       int mid = left + (right - left) / 2;
       if (condition(mid)) {
           left = mid; // Problematic mutation
       } else {
           right = mid - 1;
       }
   }
   ```
   Identifikasi kondisi tepat di mana kode di atas masuk ke dalam *infinite loop*. Bagaimana Anda mendesain pemilihan titik tengah yang *right-biased* (`mid = left + (right - left + 1) / 2`) untuk menyelesaikan masalah ini secara deterministik?

2. **Degenerasi Rotated Sorted Array dengan Duplikasi**  
   Pada pencarian elemen dalam *Rotated Sorted Array* yang berisi elemen-elemen unik (LeetCode 33), kompleksitas waktu terjamin $O(\log n)$. Namun, jika data mengandung duplikasi (LeetCode 81), kompleksitas terburuk mendegradasi menjadi $O(n)$. Tunjukkan analisis langkah mikro (step-by-step execution) dari *worst-case state* di mana algoritma kehilangan kemampuan eliminasi separuh partisi ruang pencarian.

3. **Binary Search pada Floating-Point Space (Epsilon-Based Search)**  
   Ketika menerapkan Binary Search untuk mencari akar fungsi numerik atau optimasi kontinu, kriteria terminasi sering kali menggunakan toleransi presisi `right - left > EPS` (misal $\epsilon = 10^{-7}$). Jelaskan fenomena *loss of significance* (cancellation) dan bahaya *catastrophic floating-point drift* jika iterasi diatur berbasis `EPS` dinamis vs iterasi dengan *fixed loop count* (misalnya tepat 100 iterasi).

4. **Hardware-Level Impact: Branch Misprediction & Cache-Locality**  
   Meskipun Binary Search memiliki kompleksitas teoritis $O(\log n)$, pada data berukuran sangat besar yang muat di RAM (misal ratusan megabyte), kinerjanya sering kali kalah cepat dibanding $k$-ary search atau *Branch-Free Binary Search* yang memanfaatkan instruksi `CMOV` (Conditional Move). Jelaskan mengapa *random memory jump* pada Binary Search menyebabkan degradasi L1/L2/L3 *Cache Line Misses* dan bagaimana Branch Predictor pada CPU modern tertekan oleh pola branching $50/50$ pada kondisi evaluasi pivot.

5. **Divergensi Split-Step pada Divide and Conquer (Closest Pair of Points)**  
   Pada algoritma Divide and Conquer untuk mencari *Closest Pair of Points* dalam geometri komputasi berdimensi 2D, setelah membagi ruang menjadi dua bagian dengan garis vertikal $x = \text{mid}$, mengapa kita hanya perlu memeriksa maksimal 6 hingga 7 titik tetangga untuk setiap titik di dalam *strip* selebar $2\delta$? Jelaskan signifikansi batasan geometris ini terhadap pencegahan kompleksitas waktu agar tidak terdegradasi menjadi $O(n^2)$.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Debugging Regresi Mikro-Latensi pada In-Memory Search Engine (Kasus Insiden Skala Besar)
Perusahaan Anda mengelola mesin pencarian metrik *real-time* berbasis *time-series*. Data disimpan dalam *flat buffer contiguous memory array* yang diurutkan secara strictly monotonic berdasarkan timestamp *epoch millisecond* per entitas ($N \approx 50.000.000$ entri per instans).  
Setelah rilis patch terbaru yang mengganti linear scanning lokal menjadi standard library Binary Search (`std::lower_bound`), latensi p99 query justru melonjak dari $4\text{ ms}$ menjadi $180\text{ ms}$ di bawah beban produksi 40.000 QPS, meskipun CPU utilization berada di kisaran normal.

**Pertanyaan Diagnostik:**
1. Mengapa transisi dari local linear scan (dengan segmentasi) ke global binary search pada memori berukuran gigabyte memicu lonjakan degradasi latensi p99 terkait *Translation Lookaside Buffer* (TLB) misses dan kegagalan *CPU Hardware Prefetcher*?
2. Bagaimana Anda merancang mitigasi arsitektur hibrida (*exponential search* / *galloping search* yang dikombinasikan dengan *cache-line aligned linear scan*) untuk mengembalikan latensi p99 ke target $< 5\text{ ms}$?

---

### Skenario B: Race Condition dan False Positive pada Distributed Log Bisection (Kasus Data Integrity)
Tim SRE membangun sistem otomatisasi RCA (*Root Cause Analysis*) yang bertugas mencari *commit SHA* pertama yang memicu kegagalan sistemik (*canary testing*) menggunakan prinsip Git Bisect terdistribusi melintasi klaster Kubernetes.  
Karena deployment canary berjalan secara paralel dan metrik telemetri yang dikumpulkan memiliki latensi propagasi (*eventual consistency lag* selama 30-90 detik), status validitas pipeline pengujian ($P(x) \in \{\text{Pass}, \text{Fail}\}$) bersifat non-deterministik dan melanggar sifat monotonic: fungsi status untuk urutan commit $c_1, c_2, c_3, c_4, c_5$ menghasilkan output sementara: `[Pass, Pass, Fail (Transient), Pass, Fail]`. Hal ini menyebabkan *bisection engine* memotong separuh ruang pencarian yang salah dan menetapkan commit yang tidak bersalah sebagai biang kerok insiden produksi.

**Pertanyaan Diagnostik:**
1. Formulasikan strategi verifikasi berbasis Binary Search probabilistik atau *Retry-Stabilization Boundary Window* untuk menangani *jitter* pada fungsi predikat non-monotonik sementara.
2. Jika fungsi evaluasi membutuhkan biaya eksekusi yang mahal (masing-masing uji coba memakan waktu 15 menit), bagaimana Anda merancang algoritma adaptif yang menyeimbangkan antara Binary Search paralel (*multi-pivot / speculative branch evaluation*) dan verifikasi idempotensi agar throughput pencarian tidak terhambat?

---

### Skenario C: Trade-off Arsitektur Secondary Index pada Storage Engine LSM-Tree (Kasus Arsitektur & Trade-off Sistem)
Anda sedang mendesain modul pembacaan (*reader engine*) untuk implementasi *Log-Structured Merge-tree* (LSM-Tree) kustom (mirip RocksDB). SSTable (*Sorted String Table*) berukuran 256MB disimpan pada storage NVMe. Modul memerlukan mekanisme pencarian key yang cepat di dalam blok data yang terkompresi.  
Ada dua opsi arsitektur indeks sekunder dalam memori (*in-memory block index*):
- **Opsi 1:** Full Sparse Index yang menyimpan *first key* dari setiap blok 4KB, menggunakan Binary Search standard untuk mencari blok target.
- **Opsi 2:** Two-level Index yang memadukan interpolasi linier (*Interpolation Search*) pada level metadata segmen, diikuti oleh *SIMD-accelerated vectorized linear scan* di dalam blok terpilih.

**Pertanyaan Diagnostik:**
1. Di bawah distribusi *key* seperti apa (misal: UUIDv4 vs sequential monotonically increasing auto-increment ID) Opsi 2 mengungguli Opsi 1 secara drastis, dan di bawah kondisi apa Opsi 2 dapat terdegradasi menjadi $O(n)$?
2. Buat analisis *trade-off* mendalam yang mencakup konsumsi RAM untuk indeks, beban I/O read amplification, dan *instruction pipeline efficiency* pada arsitektur CPU x86_64 modern untuk kedua pendekatan tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput SLA Anomaly Window Detector via Binary Search on Solution Space

#### Problem Description
Dalam sistem monitoring infrastruktur skala besar, Anda menerima aliran metrik latensi dari ribuan microservices. Sistem menerima sebuah array metrik berurutan waktu $A$ berisi $N$ bilangan bulat non-negatif yang merepresentasikan beban latensi per detik.  
Tim Platform Engineering menetapkan aturan SLA ketat: Anda diminta menemukan **panjang durasi jendela minimum $W$ ($1 \le W \le N$)** sedemikian rupa sehingga jika kita membagi array menjadi maksimal $K$ segmen kontigu (di mana setiap segmen merepresentasikan *batch processing window*), total beban latensi maksimum dari segmen mana pun **tidak melebihi batas toleransi kapasitas $C$**, ATAU jika batas kapasitas $C$ tidak ditentukan, carilah nilai batas beban maksimum minimum (*minimized largest split sum*) yang mungkin jika array dibagi menjadi tepat $M$ sub-array kontigu (generalisasi LeetCode 410 - Split Array Largest Sum).

Untuk tantangan level Principal Engineer ini, masalah diperluas: Anda harus mengimplementasikan komponen ini secara *zero-allocation* setelah inisialisasi, menangani *streaming burst* secara konkruen, serta menerapkan pruning berbasis Divide and Conquer untuk komputasi matriks penalti transisi window.

#### Requirements
1. **Algoritma Utama**: Implementasikan engine pencarian solusi berbasis *Binary Search on Solution Space* untuk menemukan nilai optimal secara deterministik.
2. **Optimasi Predikat**: Fungsi kelayakan predikat `isFeasible(targetCapacity, M)` harus berjalan dalam kompleksitas waktu $O(N)$ dan kompleksitas ruang tambahan $O(1)$.
3. **Komponen Rekursif Divide & Conquer**: Terapkan algoritma *Divide and Conquer Optimization* (D&C Knuth/Yao style speedup) untuk menghitung varian Dynamic Programming dari segmentasi window metrik berbobot jika jumlah partisi $K$ sangat kecil ($K \le 20$), mereduksi kompleksitas $O(K \cdot N^2)$ menjadi $O(K \cdot N \log N)$.
4. **Resiliensi Data**: Tangani skenario nilai metrik ekstrem di mana total akumulasi dapat melampaui rentang *signed 64-bit integer* tanpa menggunakan tipe data eksternal `BigInteger` (gunakan deteksi saturasi atau saturating arithmetic logic).

#### Constraints
- Ukuran array data: $1 \le N \le 10^7$
- Nilai elemen metrik: $0 \le A[i] \le 10^9$
- Jumlah segmen partisi: $1 \le M \le \min(N, 1000)$
- Target Latensi Komputasi: Engine harus mampu menyelesaikan proses komputasi untuk $N = 10^7$ dalam waktu kurang dari $350\text{ ms}$ pada arsitektur modern (single thread).
- Memory Footprint: Auxiliary memory tidak boleh melebihi $O(1)$ untuk varian Binary Search on Answer dan $O(N)$ untuk varian D&C DP.

#### Expected Output
1. Spesifikasi pseudocode atau implementasi bahasa tingkat tinggi (C++, Rust, atau Go) yang modular, menyertakan:
   - Evaluasi batas bawah (*lower bound*) dan batas atas (*upper bound*) dari ruang pencarian (*search space*).
   - Core Binary Search Loop bebas *off-by-one error* dan bebas risiko *infinite loop*.
   - Evaluator Predikat Monotonik.
2. Bukti formal invariant loop dan analisis matematis ketat mengenai kompleksitas waktu akhir: $O(N \cdot \log(\sum A[i] - \max(A[i])))$.
3. Benchmarking plan / unit test boundary case yang mencakup array seragam, array monotonik naik curam, array dengan elemen tunggal masif, dan nilai kapasitas batas kritis.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme formal penetapan invarian loop pada Binary Search dan bagaimana hubungan matematis antara representasi interval pencarian (`closed` vs `half-open`) dengan kondisi terminasi loop.
- [ ] Formulasi matematis Master Theorem (tiga kasus standar dan kasus perpanjangan/ekstensi akrual) untuk mendekonstruksi kompleksitas algoritma Divide and Conquer.
- [ ] Karakteristik *Monotonic Predicate Function* ($P(x): X \to \{0, 1\}$) dan bagaimana memetakan masalah optimasi non-terurut ke dalam domain *Binary Search on Answer Space*.
- [ ] Alasan mendasar mengapa CPU cache-line invalidation, TLB misses, dan branch mispredictions dapat mendegradasi performa bisection search pada struktur data memori berukuran masif melampaui analisis teoritis $O(\log n)$.
- [ ] Geometri pemecahan partisi ruang pada algoritma spasial Divide and Conquer (seperti batasan titik dalam *bounding box* algoritma Closest Pair of Points).

### Saya tidak perlu menghafal:
- [ ] Varian sintaksis implementasi rekursif atau iteratif khusus dari bahasa pemrograman tertentu; logika invarian dan mutasi batas adalah prinsip universal yang independen terhadap bahasa.
- [ ] Nilai eksak floating-point boundary representation untuk setiap tipe arsitektur; cukup pahami manipulasi unit *ULP (Units in the Last Place)* dan toleransi mesin $\epsilon$.
- [ ] Rumus kasus patologis/janggal di luar lingkup Master Theorem standar (misal kasus celah non-polinomial antarcabang); cukup pahami metode pohon rekursi (*recursion tree method*) dari prinsip pertama (*first principles*).

### Saya harus bisa melakukan:
- [ ] Menulis template Binary Search standar (mencari exact value, lower bound / first true, upper bound / last true) secara instan, bebas bug, dan bebas dari jebakan *off-by-one* atau *infinite loop* dalam waktu kurang dari 3 menit.
- [ ] Mengidentifikasi dan memitigasi *integer overflow bug* pada representasi biner saat melakukan kalkulasi aritmetika midpoint pointer.
- [ ] Mentransformasikan masalah optimasi industri (*Minimax / Maximin problem*) menjadi evaluasi kelayakan fungsi predikat monotonik $O(N)$.
- [ ] Mendiagnosis dan memperbaiki degradasi performa Binary Search pada sistem komputasi berkinerja tinggi yang disebabkan oleh *hardware branch misprediction* menggunakan teknik branchless code atau segmentasi data.
- [ ] Melakukan analisis formal dan pembuktian matematis terhadap algoritma Divide and Conquer kompleks menggunakan kombinasi Recurrence Relation dan Invariant Induction.