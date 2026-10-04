# BAB 09: Quiz, Challenge, & Knowledge Check
**Dynamic Programming & Exhaustive Search**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Ekuivalensi Topologis dan Directed Acyclic Graph (DAG)
Jelaskan secara matematis dan arsitektural mengapa setiap persoalan Dynamic Programming (DP) deterministik pada dasarnya dapat dimodelkan sebagai pencarian jalur terpendek (*shortest path*) atau terpanjang (*longest path*) pada sebuah *Directed Acyclic Graph* (DAG). Apa implikasi keberadaan siklus (*cycle*) dalam relasi rekurensi terhadap validitas State Transition Engine?

### Soal 1.2: Batasan Optimal Substructure
Buktikan mengapa persoalan *Shortest Simple Path* pada graf tak berarah memiliki sifat *Optimal Substructure*, sedangkan *Longest Simple Path* pada graf tak berarah yang sama **tidak** memiliki *Optimal Substructure*. Kaitkan jawaban Anda dengan independensi sub-masalah (*subproblem independence*) dan kegagalan generalisasi teknik memoization.

### Soal 1.3: Top-Down Memoization vs Bottom-Up Tabulation pada Level Microarchitecture
Bandingkan pendekatan *Top-Down with Memoization* (rekursif) dan *Bottom-Up Tabulation* (iteratif) ditinjau dari:
1. *Instruction cache (I-cache) locality* dan *branch predictor pressure*.
2. Overhead alokasi *call stack frame* versus overhead pemesanan memori di *heap*.
3. Akses memori spasial dan temporal terhadap *L1/L2 data cache lines* (stride pattern).

### Soal 1.4: Taksonomi Pemangkasan Ruang State: Exhaustive Search, Backtracking, dan Branch-and-Bound
Bedakan secara presisi mekanisme terminasi dan evaluasi state antara:
1. Pure Exhaustive Search (Generate and Test).
2. Backtracking dengan Pruning (Predikat Kelayakan / *Feasibility Pruning*).
3. Branch-and-Bound (Fungsi Pembatas / *Bounding Function* via Heuristic Relaxation).
Jelaskan bagaimana konsep *bounding function* mencegah ledakan kombinatorial (*combinatorial explosion*) sebelum sub-pohon rekursif dieksekusi secara penuh.

### Soal 1.5: Prinsip Minimalitas Formulasi State
Dalam mendesain tabel DP, seorang insinyur sering tergoda memasukkan seluruh variabel kontekstual ke dalam *tuple state* $DP(s_1, s_2, \dots, s_k)$. Jelaskan metodologi matematis untuk menentukan apakah suatu variabel wajib menjadi dimensi eksplisit dari state atau cukup diderivasi secara implisit (*derived state*) melalui invarian global. Berikan formula kompleksitas waktu dan ruang yang tereduksi akibat eliminasi dimensi tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Cache Line Thrashing pada Flattening Array Multidimensi
Diberikan kode implementasi DP 2D untuk algoritma String Alignment ($N \times M$):
```cpp
// Varian A: Row-Major Order
for (int i = 1; i <= N; ++i) {
    for (int j = 1; j <= M; ++j) {
        dp[i][j] = min({dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost(i, j)});
    }
}

// Varian B: Column-Major Order
for (int j = 1; j <= M; ++j) {
    for (int i = 1; i <= N; ++i) {
        dp[i][j] = min({dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost(i, j)});
    }
}
```
Ketika $N = 30.000$ dan $M = 30.000$ pada arsitektur x86_64 dengan L1 data cache sebesar 32 KB dan cache line 64 byte, jelaskan secara mendalam mengapa Varian B mengalami degradasi performa (*throughput collapse*) hingga puluhan kali lipat dibandingkan Varian A. Jelaskan pula dampak alokasi `std::vector<std::vector<int>>` vs flat array 1D berukuran `N * M` terhadap *pointer chasing* dan fragmentasi TLB (*Translation Lookaside Buffer*).

### Soal 2.2: Space Optimization Pitfall: 0/1 Knapsack vs Unbounded Knapsack
Perhatikan cuplikan kode optimasi memori 1D untuk Knapsack berikut:
```python
# Versi 1
for i in range(n):
    for w in range(W, weights[i] - 1, -1):
        dp[w] = max(dp[w], dp[w - weights[i]] + values[i])

# Versi 2
for i in range(n):
    for w in range(weights[i], W + 1):
        dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
```
Jelaskan perubahan semantik formal yang terjadi pada relasi dependensi state ketika arah traversal kapasitas $w$ dibalik dari menurun (*descending*) menjadi menaik (*ascending*). Mengapa kesalahan arah traversal ini secara diam-diam mengubah kompleksitas permasalahan dari *0/1 Knapsack* menjadi *Unbounded Knapsack* tanpa memicu error kompilasi atau runtime crash?

### Soal 2.3: Recursive Stack Overflow pada Top-Down DP dan Transformasi Manual Stack
Pada sistem enterprise berbasis JVM atau VNode (V8), fungsi rekursif dengan kedalaman rekursi $\ge 10^5$ akan melempar `StackOverflowError` meskipun memoization telah aktif. Rancanglah arsitektur eksekusi pengganti menggunakan *Explicit Heap-Allocated Call Stack* yang mampu mengeksekusi Top-Down DP secara non-rekursif dengan mempertahankan evaluasi state yang bersifat *post-order* (DFS).

### Soal 2.4: Instabilitas Numerik dan Underflow pada Transition Function Probabilistik
Pada *Hidden Markov Model* (Forward-Backward Algorithm) atau Viterbi Decoding dengan rantai transisi panjang ($T > 1000$), transisi state dinyatakan sebagai:
$$DP(t, v) = \sum_{u} DP(t-1, u) \cdot P(v \mid u) \cdot P(O_t \mid v)$$
Eksekusi langsung perkalian floating-point (`float64`) menyebabkan nilai terdisipasi menjadi `0.0` (*arithmetic underflow*). 
1. Tuliskan reformulasi state transition menggunakan teknik *Log-Sum-Exp* (LSE).
2. Bagaimana cara mengimplementasikan operasi LSE agar tidak mengalami overflow pada komputasi $\exp(x)$?

### Soal 2.5: Limitasi State Bitmasking dan Branch Misprediction
Pada Bitmask DP dengan $N$ elemen, state direpresentasikan menggunakan integer primitive (`uint32_t` atau `uint64_t`).
1. Analisis performa instruksi CPU bawaan seperti `__builtin_popcount`, `__builtin_ctz`, dan operasi manipulasi bit intrinsik `_pext_u64` dalam memangkas branch misprediction pada loop transisi state.
2. Jelaskan mengapa batas praktis $N$ pada arsitektur modern berhenti di kisaran $N \approx 20\dots 24$ untuk waktu pemrosesan $< 1$ detik, terlepas dari fakta bahwa tipe data `uint64_t` mampu menampung hingga $N = 64$ bit.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike pada Real-Time Multi-Item Dynamic Pricing Engine
*Konteks Insiden:*
Sebuah platform e-commerce menerapkan algoritma Knapsack multidimensi untuk menentukan bundel diskon optimal bagi pengguna yang sedang checkout secara real-time. Kapasitas maksimum pengguna dinilai dari budget saldo, batas kuota bobot logistik, dan batas kuota volume fisik. Service ditulis dalam Go dan menangani 20.000 RPS.

*Gejala:*
Saat festival belanja flash-sale, p99 latency melonjak dari 15ms menjadi 2.800ms. CPU utilization mencapai 100% dan memicu OOM (*Out Of Memory*) killer pada Kubernetes Pods. Profiling CPU via `pprof` menunjukkan alokasi memori berlebih berasal dari alokasi tabel DP matriks 3 dimensi `[budget][weight][volume]` yang dibuat per-request.

*Pertanyaan Diagnostik:*
1. Mengapa alokasi dinamis tabel DP 3D per request merupakan *anti-pattern* fatal dalam sistem berkonkurensi tinggi?
2. Usulkan mitigasi arsitektur: Bagaimana cara menerapkan *sync.Pool* memory reuse atau bounded sparse-representation tanpa mengorbankan isolasi transaksi antar pengguna?
3. Jika resolusi dimensi budget bernilai diskrit sangat besar (misal: IDR 10.000.000), bagaimana Anda mentransformasikan problem ini menjadi pendekatan *Fully Polynomial-Time Approximation Scheme* (FPTAS) agar waktu komputasi berada dalam hard SLA $< 10\text{ ms}$?

### Skenario B: Cache Stampede dan Thundering Herd pada Distributed Memoization Layer
*Konteks Insiden:*
Sebuah layanan rekomendasi konten menggunakan algoritma Dynamic Programming graf berbobot kompleks untuk menghitung *Optimal Delivery Path* aset multimedia. Untuk menghemat CPU, hasil sub-state DP di-cache pada distributed memory store (Redis Cluster).

*Gejala:*
Ketika state kunci (*root node subproblem*) mengalami *cache expiration* (TTL habis), ratusan worker node secara simultan menyimpulkan bahwa cache bernilai `NIL`. Seluruh worker kemudian serentak mengeksekusi rekursi DP penuh yang membebani cluster komputasi hingga down (*cascade failure*).

*Pertanyaan Diagnostik:*
1. Analisis kelemahan desain sistem yang mengandalkan caching terdistribusi untuk sub-state DP yang memiliki interdependensi hierarkis.
2. Rancang strategi konkurensi menggunakan *Singleflight Pattern* atau *Distributed Mutex with Double-Checked Locking* guna memastikan hanya 1 worker yang mengevaluasi sub-problem DP, sementara worker lain menunggu resolusi subproblem tersebut.
3. Bagaimana Anda menangani *deadlock* jika State $A$ membutuhkan State $B$, sementara worker lain yang memproses State $B$ membutuhkan State $A$ pada graf dependensi yang tidak strictly-acyclic akibat data kotor?

### Skenario C: Trade-off Arsitektur Exact DP vs Branch-and-Bound pada Last-Mile Dispatching
*Konteks Insiden:*
Perusahaan logistik nasional ingin mengoptimalkan rute kurir harian yang melayani 35 titik drop-off per van. Engineering team berdebat antara mengimplementasikan:
- Pendekatan 1: *Exact Bitmask DP* (Held-Karp Algorithm, waktu $O(n^2 2^n)$).
- Pendekatan 2: *Branch-and-Bound* berbasis matriks reduksi jarak (*Hungarian Algorithm / 1-Tree Relaxation*).
- Pendekatan 3: *Metaheuristic Beam Search* dengan fixed beam-width $K$.

*Pertanyaan Diagnostik:*
1. Buktikan secara matematis mengapa Pendekatan 1 (Held-Karp DP) mustahil diaplikasikan pada $N = 35$ terlepas dari seberapa besar spesifikasi server yang dialokasikan.
2. Bandingkan profil penggunaan memori antara Pendekatan 2 (*Branch-and-Bound* Best-First Search menggunakan priority queue) dan Pendekatan 3 (*Beam Search*). Pendekatan mana yang memiliki risiko *unbounded memory growth* saat runtime?
3. Sebagai Principal Architect, buat matriks keputusan evaluasi trade-off (Completeness, Optimality, Memory Footprint, Predictability of Execution Time) untuk menentukan algoritma yang paling layak masuk ke sistem production dengan SLA dispatching 30 detik.

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Throughput Memory-Bounded Constrained Shortest Path Engine (Bit-Parallel DP & Pruning)**

### Deskripsi Masalah
Anda diminta membangun komponen internal untuk mesin perutean transaksi finansial berlatensi rendah. Diberikan jaringan Directed Acyclic Graph (DAG) logis dengan $N$ *node* ($N \le 64$) dan $M$ *directed edge*. Setiap edge memiliki dua atribut:
1. `latency` (integer positif, metrik yang harus diminimalkan).
2. `cost` (integer non-negatif, biaya transaksi eksekusi).

Tujuan sistem adalah menemukan jalur dari Node $0$ ke Node $N-1$ yang meminimalkan total `latency`, dengan syarat total `cost` tidak boleh melebihi `CostBudget` yang ditentukan.

### Kebutuhan Fungsional & Teknis (Requirements)
1. **Zero Dynamic Allocation at Runtime:** Eksekusi per-query tidak boleh mengalokasi memori di heap (`malloc`, `new`, atau alokasi slice dinamis Go). Seluruh scratchpad memory harus dialokasikan di awal (*pre-allocated arena*) atau hidup di call stack.
2. **Bit-Parallel Reachability Check:** Sebelum mengeksekusi transisi state, mesin harus melakukan bitwise reachability check menggunakan representasi bitmask 64-bit untuk memastikan bahwa dari node saat ini, node tujuan $N-1$ memang dapat dijangkau dalam sisa budget yang ada.
3. **Dual Execution Engine:**
   - Gunakan Top-Down DP dengan Branch-and-Bound Pruning jika graph bersifat sparse.
   - Gunakan Bottom-Up Tabulation berbasis Topological Order jika graph bersifat dense.
4. **State Formulation:** State didefinisikan sebagai $DP(u, c)$, yaitu latency minimum untuk mencapai node tujuan $N-1$ dari node $u$ dengan sisa budget $c$.

### Batasan Sistem (Constraints)
- $N \le 64$ (Setiap node dapat diindeks menggunakan bit `0` sampai `63`).
- $M \le 1.000$.
- $\text{latency}(e) \ge 1$, untuk setiap edge $e$.
- $\text{cost}(e) \ge 0$, untuk setiap edge $e$.
- $\text{CostBudget} \le 500$.
- Waktu eksekusi maksimum per query: **$< 250 \text{ microseconds}$** pada single thread CPU server modern (e.g., AMD EPYC / Intel Xeon).
- Memory Footprint engine: **$\le 8 \text{ MB}$ persistent scratchpad**.

### Spesifikasi Input/Output
- **Input:** 
  - `adj_list`: Representasi graph (node tujuan, latency, cost).
  - `source`: Integer (selalu `0`).
  - `target`: Integer (selalu `N - 1`).
  - `budget`: Integer.
- **Output:** 
  - `struct ExecutionResult { int64_t min_latency; uint64_t path_mask; bool feasible; }`
  - `path_mask` adalah bitmask 64-bit yang menandai node-node yang dikunjungi pada jalur optimal. Jika ada beberapa jalur bernilai latency sama, pilih jalur dengan cost terendah. Jika tidak ada jalur valid, kembalikan `feasible = false`.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan pemahaman Anda sebelum melangkah ke topik Advanced Algorithmic Systems.

### Saya harus memahami:
- [ ] Karakteristik formal permasalahan yang menolak penyelesaian Greedy namun tunduk pada Dynamic Programming (pelanggaran *Greedy Choice Property*).
- [ ] Perbedaan esensial kompleksitas waktu polinomial murni ($O(N^k)$) dengan pseudo-polinomial ($O(N \cdot W)$ pada kasus Knapsack/Subset-Sum) ditinjau dari ukuran representasi input bit.
- [ ] Hubungan antara Top-Down DP state caching dan memoization table lifecycle pada concurrent processing.
- [ ] Pengaruh orientasi penyimpanan data (*Row-Major* vs *Column-Major*) terhadap frekuensi L1 data-cache misses saat eksekusi nested loop DP.
- [ ] Cara mengabstraksi constraint kombinatorial ke dalam compact representation menggunakan *Bitmask Manipulation* ($1 \ll i$, popcount, trailing zeros).
- [ ] Prinsip *Branch-and-Bound* berbasis relaksasi batas (*upper/lower bounding*) untuk memotong rantai evaluasi NP-Hard search space tree.

### Saya tidak perlu menghafal:
- [ ] Nama-nama spesifik ratusan variasi soal DP di platform LeetCode (e.g., "House Robber VII", "Coin Change IV").
- [ ] Sintaks mikro bitwise intrinsik untuk compiler non-standar (cukup pahami semantik komputasi bitwise dasarnya).
- [ ] Kode template boilerplate eksekusi DP tanpa memahami struktur DAG yang mendasari relasi dependensinya.

### Saya harus bisa melakukan:
- [ ] Menurunkan persamaan matematis relasi rekurensi (*Bellman Equation*) secara presisi dari deskripsi problem bisnis yang ambigu.
- [ ] Menganalisis *State Dependency Graph* untuk membuktikan ada atau tidaknya siklus siklik (*cyclic dependencies*) sebelum menulis kode.
- [ ] Melakukan teknik optimasi ruang (*space complexity reduction*) dari matriks 2D $O(N \times M)$ menjadi dua baris atau satu flat buffer $O(M)$ dengan benar tanpa corrupting read-after-write dependencies.
- [ ] Memprofil performa runtime eksekusi program DP menggunakan profiler CPU hardware counter (seperti `perf` untuk melacak `L1-dcache-load-misses` dan `branch-misses`).
- [ ] Mengonversi rekursi naive $O(2^N)$ menjadi DP teroptimasi atau membuktikan secara matematis bahwa problem tersebut membutuhkan pendekatan aproksimasi heuristik karena sifat dasar eksplorasi ruang state-nya.