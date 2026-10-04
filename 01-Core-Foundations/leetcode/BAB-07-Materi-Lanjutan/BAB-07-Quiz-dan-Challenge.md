# BAB 07: Quiz, Challenge, & Knowledge Check
**Graph Theory & Network Topologies**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Representasi Memori Graf dan Cache Locality
Bandingkan representasi graf menggunakan **Adjacency Matrix**, **Adjacency List (berbasis pointer/linked list)**, dan **Compressed Sparse Row (CSR)** dalam konteks:
1. Kompleksitas ruang teoritis vs konsumsi memori aktual pada arsitektur CPU 64-bit modern.
2. Dampak terhadap *CPU L1/L2 cache hit rate* saat melakukan traversal Breadth-First Search (BFS) pada graf berskala besar ($|V| > 10^6, |E| > 10^7$).
3. Kemudahan mutasi graf secara *in-place* (penambahan/penghapusan *edge* secara dinamis).

### Soal 1.2: Invarian Traversal dan Karakteristik State Space
Pada algoritma traversal graf:
1. Mengapa konsumsi memori terburuk (*worst-case space complexity*) BFS pada graf reguler dengan derajat percabangan (*branching factor*) $b$ dan kedalaman $d$ adalah $O(b^d)$, sedangkan DFS adalah $O(d)$?
2. Jelaskan mengapa deteksi siklus (*cycle detection*) pada **Directed Graph** memerlukan 3-state tracking (*White-Gray-Black* / *Unvisited-Visiting-Visited*), sedangkan pada **Undirected Graph** cukup menggunakan 2-state tracking (*Visited/Unvisited*) ditambah pengecekan *parent pointer*.

### Soal 1.3: Mekanisme Relaksasi dan Batasan Kelemahan Jalur Terpendek
Dalam algoritma jalur terpendek (*Single-Source Shortest Path*):
1. Definisikan secara matematis operasi **Edge Relaxation** dan jelaskan mengapa algoritma Dijkstra gagal menghasilkan solusi optimal jika graf memiliki *negative edge weight*, meskipun tidak ada *negative cycle*.
2. Buktikan secara formal mengapa algoritma Bellman-Ford memerlukan tepat $|V| - 1$ iterasi relaksasi penuh untuk menjamin konvergensi jalur terpendek pada Directed Acyclic Graph (DAG) maupun graf berarah umum tanpa siklus negatif.

### Soal 1.4: Asimtotik Disjoint Set Union (DSU) dan Fungsi Ackermann
Pada struktur data Disjoint Set Union (DSU / Union-Find):
1. Jelaskan perbedaan peran optimasi **Union by Rank/Size** versus **Path Compression**.
2. Mengapa kombinasi kedua teknik tersebut menurunkan kompleksitas waktu teramortisasi per operasi menjadi $O(\alpha(n))$ (di mana $\alpha$ adalah *Inverse Ackermann Function*)? Apa yang terjadi pada kompleksitas waktu jika hanya *Path Compression* yang diimplementasikan tanpa *Union by Rank* pada skenario terburuk (*adversarial inputs*)?

### Soal 1.5: Dualitas Algoritma Pohon Rentang Minimum (MST)
Berdasarkan **Cut Property** dan **Cycle Property** dalam Graph Theory:
1. Turunkan logika kebenaran (*correctness proof*) dari algoritma **Kruskal** vs algoritma **Prim**.
2. Pada densitas graf seperti apa ($|E| \approx |V|$ vs $|E| \approx |V|^2$) algoritma Prim yang dioptimalkan dengan *Fibonacci Heap* mengungguli Kruskal yang menggunakan *sorting* $O(|E| \log |E|)$? Jelaskan alasan praktis mengapa industri perangkat lunak hampir selalu lebih memilih Kruskal atau Prim berbasis *Binary Heap* standar dibanding *Fibonacci Heap*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Overhead Pointers pada Graph Traversal
Seorang engineer mengimplementasikan struktur data graf pada Go/Java untuk memproses graf jalan raya dengan $10.000.000$ *node* dan $30.000.000$ *directed edge*. Setiap node dimodelkan sebagai objek:
```java
class Node {
    long id;
    List<Edge> neighbors = new ArrayList<>();
}
class Edge {
    Node target;
    int weight;
}
```
Saat graf dimuat, proses mengalami *Out of Memory* (OOM) pada JVM dengan alokasi heap 4 GB, padahal perhitungan data mentah:
- Node: $10^7 \times 8\text{ bytes} \approx 80\text{ MB}$
- Edge: $3 \times 10^7 \times (8 + 4)\text{ bytes} \approx 360\text{ MB}$
Total data teoritis $< 500\text{ MB}$.
**Pertanyaan:** Bedah struktur memori internal objek JVM (object header, reference pointer padding, layout `ArrayList` array doubling & boxing) yang menyebabkan fenomena amplifikasi memori ini, dan rancang representasi data alternatif berbasis *flat primitive array* (`int[]`) untuk memangkas penggunaan heap di bawah 1 GB.

### Soal 2.2: Pitfalls pada Bidirectional BFS
Dalam implementasi **Bidirectional BFS** untuk mencari jalur terpendek pada graf tanpa bobot (*unweighted*):
1. Kapan tepatnya proses terminasi harus dilakukan: Apakah seketika saat *frontier* dari *source* menyentuh *node* yang sudah dikunjungi oleh *frontier* dari *target*, atau setelah seluruh level saat ini selesai diekspansi? Berikan *counter-example* yang membuktikan bahwa terminasi dini yang salah dapat menghasilkan jalur suboptimal.
2. Bagaimana strategi ekspansi *frontier* yang optimal untuk meminimalkan *state space explosion*: apakah bergantian secara kaku ($1:1$) atau berbasis rasio ukuran *frontier* saat ini ($\min(|Q_{\text{forward}}|, |Q_{\text{backward}}|)$)?

### Soal 2.3: Iterative Tarjan's Strongly Connected Components (SCC)
Algoritma Tarjan untuk SCC umumnya diajarkan secara rekursif menggunakan dua nilai: `discovery_time[u]` dan `low_link[u]`.
1. Apa akar masalah kegagalan sistemik jika implementasi rekursif ini dijalankan pada graf dependensi microservice berskala besar dengan rantai dependensi sedalam 500.000 *node*?
2. Saat mengubah algoritma Tarjan dari rekursif menjadi iteratif menggunakan *explicit stack*, jelaskan bagaimana Anda merekayasa transisi kembali (*post-order step*) untuk menghitung nilai `low_link[u] = min(low_link[u], low_link[v])` secara tepat tanpa merusak siklus eksekusi stack DFS.

### Soal 2.4: State Space Explosion pada Multi-Criteria Shortest Path
Anda diminta mencari rute terpendek antar dua titik pada graf multimodal di mana setiap *edge* memiliki dua bobot independen: `latency` (ms) dan `monetary_cost` ($). Tujuannya adalah mencari latensi minimum dengan batasan total biaya $\le B$.
1. Mengapa algoritma Dijkstra standar tidak bisa langsung diterapkan hanya dengan mengubah fungsi pembanding *priority queue*?
2. Bagaimana cara memodelkan ulang *state graph* ini agar Dijkstra dapat digunakan? Apa konsekuensi perluasan ruang keadaan (*state explosion*) terhadap kompleksitas waktu dan memori algoritma yang baru?

### Soal 2.5: Deadlock Detection Engine pada Directed Acyclic Graph (DAG) Dinamis
Sebuah sistem task engine menerima penambahan dependensi antar-task secara dinamis dan konkuren melalui API `add_dependency(task_A, task_B)`. Penambahan edge ditolak jika menyebabkan siklus (*deadlock*).
1. Mengapa melakukan pemeriksaan DFS/Kahn penuh berbiaya $O(V + E)$ pada setiap pemanggilan `add_dependency` menjadi *throughput bottleneck* utama pada sistem dengan ribuan edge per detik?
2. Rancang mekanisme inkremental (seperti *Topological Order Maintenance* atau algoritma *Pearce-Kelly*) untuk memvalidasi siklus secara lokal tanpa perlu melakukan traversal ulang dari *root node*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Graph Traversal Bottleneck & Supernode Problem
**Konteks Sistem:**
Anda adalah Performance Architect pada jejaring sosial B2B skala global. Sistem memiliki fitur rekomendasi *"Who viewed your profile within 3 hops"* yang dihitung secara *near-real-time* via distributed in-memory graph service. Graf memiliki 500 juta node dan 20 miliar edge, disimpan dalam partisi terdistribusi berdasarkan konsistensi hash `node_id`.

**Insiden:**
Setiap kali traversal BFS mencapai profil akun korporasi besar atau selebriti (*supernode* dengan derajat keluar/masuk $> 2.000.000$ koneksi), mesin pekerja (*worker nodes*) mengalami lonjakan latensi P99 dari 20 ms menjadi 12.000 ms, disusul oleh kegagalan *Garbage Collection pause* (Stop-the-World) dan degradasi *cluster wide*.

**Pertanyaan Diagnostik & Solusi:**
1. Analisis mekanisme kegagalan sistem: Mengapa keberadaan *supernodes* menghancurkan konkurensi dan pemanfaatan memori pada distributed BFS?
2. Rancang arsitektur traversal adaptif (*Degree-Aware Graph Traversal*) yang memitigasi dampak *supernode* tanpa mengorbankan integritas data rekomendasi.
3. Bagaimana Anda mempartisi ulang graf terdistribusi (*Graph Partitioning*) untuk menghindari fenomena *high-edge-cut overhead* ketika *supernode* harus dibaca oleh banyak worker node secara bersamaan?

---

### Skenario B: Race Condition dan Routing Loops pada Dynamic Service Mesh
**Konteks Sistem:**
Sebuah arsitektur Service Mesh internal menggunakan implementasi protokol link-state terdistribusi yang mirip dengan OSPF/IS-IS untuk merutekan lalu lintas antar-pod di ribuan node Kubernetes. Setiap node secara berkala mengeksekusi algoritma Dijkstra lokal untuk memperbarui *routing table* kernel (eBPF map) berdasarkan metrik latensi *edge* yang diukur secara dinamis.

**Insiden:**
Ketika terjadi *network flapping* (koneksi antar-node putus-nyambung dengan frekuensi tinggi di beberapa availability zone), terdeteksi lonjakan packet loss hingga 35%. Analisis paket jaringan menunjukkan adanya **Transient Routing Loops**: paket data berputar tanpa henti antara node $X$, $Y$, dan $Z$ hingga TTL (*Time to Live*) habis, meskipun algoritma Dijkstra pada masing-masing node terbukti benar secara matematis.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah akar penyebab timbulnya *transient routing loop* pada sistem terdistribusi ini meskipun seluruh node mengeksekusi Dijkstra yang benar.
2. Mengapa propagasi update graf asinkron menyebabkan inkoherensi pandangan topologi (*asymmetric topology views*) antar node?
3. Rancang protokol konvergensi atau mekanisme pertukaran status yang menjamin *loop-free routing* selama fase transisi *network flapping* (misalnya: pendekatan berbasis *Ordered Fib Updates*, *Loop-Free Alternates (LFA)*, atau sinkronisasi berbasis *Epoch Versioning*).

---

### Skenario C: Incremental Dependency Resolution pada Build Engine Monorepo
**Konteks Sistem:**
Anda mendesain *core engine* untuk sistem CI/CD Monorepo berskala enterprise (seperti Bazel atau Turborepo). Graf dependensi build terdiri dari $2.000.000$ target build (node) dan $8.000.000$ relasi dependensi (edge).

**Tantangan Arsitektur:**
Developer melakukan *commit* yang mengubah kode pada target $T$. Sistem harus:
1. Mendeteksi secara instan seluruh target yang terdampak (*transitive downstream dependents*).
2. Mengeksekusi kompilasi secara paralel maksimal dengan memanfaatkan CPU multi-core, tanpa melanggar batasan dependensi (*DAG topological constraints*).
3. Mendukung fitur *early cut-off*: Jika build dari target $T_i$ menghasilkan artefak *output hash* yang identik dengan versi sebelumnya (misalnya hanya modifikasi komentar kode), eksekusi downstream target dari $T_i$ harus dibatalkan dari antrean eksekusi dan dianggap *up-to-date* secara instan.

**Pertanyaan Diagnostik & Solusi:**
1. Struktur data graf apa yang paling efisien untuk memetakan dependensi dua arah (*upstream dependencies* untuk build order vs *downstream dependencies* untuk invalidation propagation) dalam batas memori server CI standar ($16\text{ GB}$ RAM)?
2. Rancang algoritma penjadwalan eksekusi paralel berbasis *dynamic topological sort* yang mendukung *reactive cancellation / early cut-off* secara thread-safe tanpa menggunakan *global lock* yang memblokir antrean worker thread.
3. Bagaimana Anda menangani *diamond dependency* (misal: $A$ bergantung pada $B$ dan $C$; $B$ dan $C$ bergantung pada $D$) agar target $A$ tidak dieksekusi sebelum kedua cabang $B$ dan $C$ tuntas, sekaligus mencegah redundansi kompilasi?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Concurrent DAG Engine with Real-Time Cycle Prevention

#### Deskripsi Masalah
Rancang dan implementasikan sebuah *In-Memory Dynamic Dependency Scheduler Engine* berkinerja tinggi. Sistem harus mampu menerima registrasi task, mendaftarkan edge dependensi antar-task secara dinamis melalui lingkungan *multi-threaded*, memvalidasi siklus secara instan sebelum edge disetujui, dan mengeksekusi task yang siap secara paralel menggunakan worker pool thread.

#### Persyaratan Fungsional
1. **Dynamic Edge Insertion with Cycle Rejection:**
   - Menyediakan API: `AddEdge(fromTaskID, toTaskID) -> Result<Success, CycleDetectedError>`.
   - Jika penambahan edge membuat siklus pada graf, tolak operasi tersebut seketika, kembalikan error, dan pastikan kondisi graf tidak mengalami korupsi.
2. **Concurrent Execution Pipeline:**
   - Menyediakan API: `SubmitTask(taskID, executionPayload)`.
   - Node yang tidak memiliki dependensi yang belum selesai (*in-degree* $0$ relatif terhadap state eksekusi) harus langsung dikirim ke antrean eksekusi worker pool.
   - Segera setelah suatu task selesai dieksekusi, status diteruskan ke task downstream. Task yang seluruh dependensinya sudah selesai harus otomatis dipicu (*cascade execution*).
3. **Execution State Resilience:**
   - Tangani skenario kegagalan: Jika sebuah task mengembalikan status `FAILED`, batalkan seluruh downstream transitive dependency dari task tersebut secara otomatis dan beri tanda `SKIPPED_DUE_TO_UPSTREAM_FAILURE`. Task lain yang tidak berhubungan harus tetap berjalan normal.

#### Batasan Arsitektur & Kinerja (Constraints)
- **Bahasa Pemrograman:** Go, Rust, C++, atau Java/C# (hindari bahasa interpretasi dinamis tanpa dukungan native threading murni).
- **Concurrency:** Tidak diizinkan membungkus seluruh graf dengan satu *global read-write mutex* (`sync.RWMutex` global). Anda harus menggunakan *fine-grained per-node locking*, *lock-free primitives* (Atomic CAS), atau *Concurrent Partitioned Structures*.
- **Volume Uji:**
  - Jumlah task: $|V| = 100.000$.
  - Jumlah dependensi dinamis: $|E| = 500.000$.
  - Thread worker paralel: 16 sampai 64 thread concurrent.
- **Latency Target:** Operasi `AddEdge` harus selesai dalam rata-rata waktu sub-milidetik ($< 1\text{ ms}$ untuk P95).
- **Memory Constraint:** Penggunaan memori total untuk menampung graf tidak boleh melebihi $512\text{ MB}$.

#### Format Luaran yang Diharapkan
1. **Struktur Data Core:** Kode definisi struct/class graf yang memuat layout memori efisien untuk node, edge, in-degree counters, dan synchronization primitives.
2. **Logika Algoritma:** Implementasi fungsi `AddEdge` (termasuk algoritma cycle check dinamis) dan fungsi `WorkerEventLoop` / `OnTaskCompleted`.
3. **Analisis Kompleksitas & Concurrency Proof:** Penjelasan ringkas mengapa arsitektur yang Anda pilih bebas dari kondisi *race condition* dan *deadlock*, serta perhitungan matematis kompleksitas waktu untuk deteksi siklus inkremental.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan Anda dalam topik Graph Theory tingkat *production/staff engineer*.

### Saya harus memahami:
- [ ] Representasi memori graf: Trade-off memori dan *cache locality* antara Adjacency Matrix, Adjacency List (array of vectors vs linked list), dan Compressed Sparse Row (CSR).
- [ ] Karakteristik DFS vs BFS: Ruang pencarian (*state space*), konsumsi memori terburuk, pola penggunaan memory queue vs call stack, serta variasinya (IDDFS - *Iterative Deepening DFS*).
- [ ] Deteksi Siklus (*Cycle Detection*): Perbedaan implementasi deteksi siklus pada Undirected Graph (DSU / 2-state DFS) vs Directed Graph (Kahn's Algorithm / 3-color DFS).
- [ ] Topological Sorting: Mekanisme algoritma Kahn berbasis in-degree vs Tarjan/DFS post-order traversal serta aplikasinya pada resolusi dependensi.
- [ ] Invarian Single-Source Shortest Path (SSSP): Mengapa Dijkstra membutuhkan bobot non-negatif, mekanisme konvergensi Bellman-Ford, dan cara kerja optimasi SPFA (*Shortest Path Faster Algorithm*).
- [ ] Pohon Rentang Minimum (*Minimum Spanning Tree*): Pembuktian *Cut & Cycle Properties*, trade-off antara algoritma Kruskal ($E \log E$) dan Prim ($V \log V + E$).
- [ ] Teori Komponen Terkoneksi Kuat (*Strongly Connected Components*): Alur logika algoritma Tarjan dan Kosaraju-Sharir berbasis *low-link* dan transposisi graf.
- [ ] Struktur Data Disjoint Set Union (DSU): Bukti matematis pemanfaatan *path compression* dan *rank-based union* yang menghasilkan kompleksitas $\alpha(n)$.

### Saya tidak perlu menghafal:
- [ ] Implementasi manual *Fibonacci Heap*: Mengetahui batasan teoritisnya cukup ($O(1)$ amortized insertion & decrease-key); dalam implementasi nyata, overhead pointer dan konstanta tersembunyi membuatnya kalah cepat dibanding *Binary Heap* cache-friendly.
- [ ] Angka eksak representasi *Inverse Ackermann Function* $\alpha(n)$: Cukup memahami bahwa nilainya $\le 4$ untuk seluruh input yang realistis di alam semesta fisik ($n \le 10^{80}$).
- [ ] Detail algoritma *Planarity Testing* atau *Four Color Theorem*: Jarang relevan untuk kebutuhan backend platform dan computational coding interview standar, kecuali bergerak di bidang computational geometry murni.

### Saya harus bisa melakukan:
- [ ] Mengonversi rekursi DFS dalam menjadi bentuk iteratif berbasis *explicit vector/stack* untuk mencegah *stack overflow* pada rantai graf ekstrem ($N > 100.000$).
- [ ] Memilih secara tepat algoritma SSSP berdasarkan karakteristik input: Unweighted (BFS $O(V+E)$), DAG (Topological + DP $O(V+E)$), Non-negative weights (Dijkstra $O(E \log V)$), Arbitrary weights with negative cycle detection (Bellman-Ford $O(VE)$).
- [ ] Mendiagnosis dan mengeliminasi *concurrency bottleneck* serta masalah *supernode* pada pemrosesan graf berskala terdistribusi.
- [ ] Mengimplementasikan representasi graf hemat memori berbasis *primitive flat arrays* (CSR style atau flattened arrays) untuk melewati kendala *Garbage Collection pause* pada runtime berbasis *managed memory* (Java/Go).
- [ ] Merancang algoritma Topological Order dinamis yang mampu mendeteksi siklus dan menjadwalkan task paralel tanpa memblokir thread engine melalui *global locking*.