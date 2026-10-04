# BAB 10: Quiz, Challenge, & Knowledge Check
**Advanced Graph Algorithms: Shortest Paths, Minimum Spanning Tree (MST), & Disjoint Set Union (DSU)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Invariant Greedy pada Dijkstra dan Kegagalannya pada Bobot Negatif
Algoritma Dijkstra beroperasi di bawah premis invarian *greedy*: ketika sebuah simpul $u$ diekstraksi dari *priority queue* (telah ditandai *visited/settled*), jarak terpendek dari *source* ke $u$ ($d[u]$) dijamin telah optimal dan bersifat final. 
* Jelaskan secara matematis dan struktural mengapa keberadaan satu saja bobot sisi negatif ($w(e) < 0$) dapat merusak invarian ini!
* Mengapa penambahan sebuah konstanta skalar positif $C$ ke seluruh bobot sisi ($w'(u, v) = w(u, v) + C$) untuk mengeliminasi nilai negatif bukanlah solusi valid untuk mencari *shortest path*?

### Soal 1.2: Mekanisme Amortisasi Disjoint Set Union (DSU)
Struktur data *Disjoint Set Union* (DSU) mencapai kompleksitas waktu amortisasi per operasi sebesar $\mathcal{O}(\alpha(n))$, di mana $\alpha$ adalah *Inverse Ackermann Function*.
* Uraikan kontribusi mekanis masing-masing dari teknik *Path Compression* (pada operasi `find`) dan *Union by Rank / Size* (pada operasi `union`) terhadap perataan pohon!
* Apa yang terjadi pada kompleksitas waktu teoritis terburuk (*worst-case*) per operasi jika hanya menerapkan *Path Compression* tanpa *Union by Rank*, atau sebaliknya?

### Soal 1.3: Prinsip Relaksasi Dinamis pada Bellman-Ford
Algoritma Bellman-Ford melakukan proses relaksasi untuk semua sisi $|E|$ sebanyak $|V| - 1$ kali.
* Buktikan secara induktif mengapa $|V| - 1$ iterasi relaksasi selalu cukup untuk menemukan jalur terpendek pada graf berarah tanpa siklus negatif!
* Bagaimana tepatnya iterasi ke-$|V|$ digunakan untuk membuktikan keberadaan siklus negatif (*negative cycle*), dan mengapa keberadaan siklus negatif yang *unreachable* dari *source* tidak terdeteksi jika inisialisasi $d[v] = \infty$ dipertahankan secara ketat?

### Soal 1.4: Cut Property vs. Cycle Property pada Minimum Spanning Tree (MST)
Konstruksi *Minimum Spanning Tree* (MST) bersandar pada dua fondasi teoritis utama: *Cut Property* dan *Cycle Property*.
* Formulasikan definisi formal dari kedua properti tersebut!
* Tunjukkan bagaimana Algoritma Prim mengeksploitasi *Cut Property* secara lokal pada setiap langkahnya, sementara Algoritma Kruskal secara implisit memanfaatkan *Cycle Property* untuk menolak sisi tertentu!

### Soal 1.5: Rekursi Subproblem pada Algoritma Floyd-Warshall
Algoritma Floyd-Warshall memecahkan masalah *All-Pairs Shortest Path* (APSP) menggunakan pemrograman dinamis dengan relasi rekurensi:
$$D^{(k)}[i][j] = \min\left(D^{(k-1)}[i][j],\, D^{(k-1)}[i][k] + D^{(k-1)}[k][j]\right)$$
* Jelaskan signifikansi semantik dari indeks $k$ pada ruang status tiga dimensi tersebut!
* Mengapa dimensi $k$ dapat dieliminasi secara aman dalam implementasi praktis menjadi matriks 2D tanpa memicu efek samping pembaruan data prematur (*dirty reads*) pada iterasi yang sama?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Overhead `Decrease-Key` vs. *Lazy Deletion* pada Dijkstra
Pada implementasi standar Dijkstra menggunakan *binary min-heap*, operasi modifikasi bobot simpul yang telah ada di dalam antrean membutuhkan fungsi `decrease-key`, yang membutuhkan pemeliharaan *lookup table index* simpul ke elemen heap ($\mathcal{O}(\log V)$). Alternatif umum pada *runtime* modern adalah *Lazy Deletion* (memasukkan pasangan `(jarak_baru, simpul)` baru ke heap dan mengabaikan entri usang saat di-`pop`).
* Analisis dampak konsumsi memori dan kompleksitas waktu dari pendekatan *Lazy Deletion* pada graf padat (*dense graph* di mana $|E| \approx |V|^2$)!
* Pada skenario sistem dengan batasan memori ketat (*embedded system*), mengapa *Indexed Priority Queue* wajib dipilih dibanding *Lazy Deletion*?

### Soal 2.2: Degenerasi Kinerja DSU pada Struktur Paralel & Persisten
Dalam implementasi konkurensi tinggi, teknik *Path Compression* klasik (`parent[x] = find(parent[x])`) menyebabkan operasi mutasi baca-tulis (*read-and-write*) pada pohon referensi yang mengakibatkan *cache line invalidation* masif antar-core CPU.
* Bagaimana Anda mendesain struktur data DSU yang *thread-safe* tanpa menggunakan *coarse-grained mutex* yang melumpuhkan throughput?
* Jika DSU harus bersifat persisten (*fully persistent DSU* dengan histori *state rollback*), mengapa *Path Compression* dilarang dan bagaimana *Union by Rank* diimplementasikan menggunakan *balanced search tree* atau *persistent array*?

### Soal 2.3: Titik Kritis Performa Kruskal vs. Prim Terhadap Densitas Graf
Diberikan dua graf: Graf A adalah jaringan jalan pedesaan berbentuk *sparse* ($|V| = 100.000$, $|E| = 150.000$), sedangkan Graf B adalah jaringan sirkuit terintegrasi berbentuk *ultra-dense* ($|V| = 20.000$, $|E| \approx 190.000.000$).
* Uraikan secara detail mengapa Algoritma Prim berbasis *adjacency matrix* murni tanpa heap berkinerja $\mathcal{O}(V^2)$ mengungguli Prim berbasis *binary heap* $\mathcal{O}(E \log V)$ dan Kruskal berbasis *sorting* $\mathcal{O}(E \log E)$ pada Graf B!
* Jelaskan bagaimana *memory locality* dan *CPU cache line prefetching* memengaruhi perbedaan performa aktual kedua algoritma tersebut pada arsitektur perangkat keras modern!

### Soal 2.4: Debugging SPFA (*Shortest Path Faster Algorithm*) Menghadapi *Pathological Graphs*
SPFA merupakan optimasi berbasis antrean (*queue-based*) dari Bellman-Ford yang memiliki kompleksitas rata-rata $\mathcal{O}(E)$. Namun, beberapa topologi graf dapat memaksa SPFA mengalami degenerasi performa menjadi eksponensial atau $\mathcal{O}(V \cdot E)$.
* Rekonstruksi bentuk topologi graf (*pathological worst-case topology*) yang dapat merusak heuristik antrean FIFO pada SPFA!
* Kebijakan pembaruan antrean apa (misal: *Small Label First* [SLF] atau *Large Label First* [LLF]) yang dapat memitigasi degradasi performa ini, dan apa kelemahan teoretisnya terhadap siklus negatif?

### Soal 2.5: Identifikasi & Ekstraksi Jalur Siklus Negatif (*Arbitrage Detection Bug*)
Sebuah mesin deteksi arbitrase valuta asing menggunakan matriks nilai tukar yang ditransformasikan ke bentuk bobot $-\log(\text{rate})$ dan dievaluasi menggunakan Bellman-Ford. Selama pengujian, sistem melaporkan adanya siklus negatif, tetapi ketika fungsi *backtracking* rekonstruksi siklus dijalankan melalui *predecessor array* (`parent[]`), program mengalami *infinite loop* yang tidak pernah mencapai simpul awal.
* Identifikasi cacat logika (*logical bug*) internal pada algoritma rekonstruksi *predecessor* yang memicu kondisi *infinite loop* tersebut!
* Tuliskan urutan algoritma yang benar untuk mengekstraksi simpul-simpul yang secara presisi membentuk siklus negatif terisolasi tanpa terjebak pada rantai *tail* yang mengarah ke siklus tersebut!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike pada Dynamic Route Engine (Service Mesh P2P)
Sebuah sistem *Service Mesh* terdistribusi berskala besar mengelola perutean internal untuk $15.000$ *microservices*. Topologi perutean direpresentasikan sebagai graf berarah dengan bobot sisi dinamis yang merepresentasikan latensi jaringan $p99$ secara *real-time*. Bobot sisi dimutasi setiap $50\text{ ms}$ berdasarkan metriks telemetri.
* **Gejala Insiden:** Setiap kali terjadi fluktuasi latensi global atau putusnya *link* transmisi data, sistem melakukan kalkulasi ulang jalur terpendek dari setiap simpul *gateway* menggunakan Dijkstra klasik berbasis *lazy deletion*. Hal ini menyebabkan *CPU utilization* melonjak ke $100\%$, latensi kalkulasi membengkak dari $2\text{ ms}$ menjadi $350\text{ ms}$, dan terjadi *packet drop* masif karena keterlambatan pembaruan tabel rute (*routing table stale*).
* **Tugas Diagnostik & Arsitektural:**
  1. Identifikasi *computational bottleneck* dari pemanggilan Dijkstra independen secara berulang dari *scratch* pada topologi yang hanya mengalami perubahan bobot marginal!
  2. Rancang strategi algoritma rute dinamis alternatif (misalnya: *Dynamic Shortest Path Algorithm* / *Incremental Shortest Path* / Algoritma D* Lite / Bounded Dijkstra) untuk memproses mutasi bobot sisi tanpa mengkalkulasi ulang seluruh graf dari nol!

### Skenario B: Race Condition & Invalid Cluster Isolation pada Dynamic Graph Partitioning
Sebuah platform analitik media sosial memproses *stream* jutaan *event* per detik untuk melacak pembentukan klaster percakapan interaktif menggunakan struktur data Disjoint Set Union (DSU) terdistribusi di memori.
* **Kondisi Sistem:** Beberapa *worker thread* secara paralel memanggil fungsi `union(u, v)` ketika mendeteksi interaksi antarpengguna, sementara *thread* monitor mengeksekusi `find(u) == find(v)` untuk mengisolasi sub-graf yang diduga mengalami polarisasi atau serangan bot.
* **Insiden Integritas:** Audit data mendeteksi bahwa beberapa klaster independen secara keliru bergabung menjadi satu *giant component*, dan pada skenario tertentu, pemanggilan `find()` menghasilkan *segmentation fault* atau perulangan tanpa henti (*infinite cyclic pointer traversal*) pada lingkungan *multi-core*.
* **Tugas Diagnostik & Solusi:**
  1. Bedah secara mekanis bagaimana *race condition* pada manipulasi *pointer* `parent` dalam *Path Compression* non-atomik dapat menciptakan siklus langsung ($A \to B \to A$) pada representasi pohon DSU!
  2. Susun rancangan struktur DSU *wait-free* atau *lock-free* menggunakan operasi atomik *Compare-And-Swap* (CAS) untuk operasi `find` dan `union` yang menjamin konsistensi linier (*linearizability*) tanpa mengorbankan performa paralel!

### Skenario C: Trade-off Arsitektur Sistem Navigasi Skala Benua
Sebuah perusahaan logistik global membutuhkan sistem kalkulasi rute navigasi untuk armada kendaraan di seluruh benua Eropa ($|V| \approx 50.000.000$ persimpangan jalan, $|E| \approx 120.000.000$ ruas jalan). Kebutuhan sistem mencakup:
1. *Query time* waktu tempuh terpendek harus di bawah $10\text{ ms}$ per permintaan pada infrastruktur server standar.
2. Bobot sisi memperhitungkan profil batas kecepatan kendaraan yang berbeda (truk kontainer, van listrik, sepeda motor).
3. Konsumsi memori RAM per proses harus efisien agar dapat dijalankan pada *multi-tenant architecture*.
* **Tugas Arsitektur & Trade-off:**
  1. Evaluasi secara kritis mengapa algoritma standar Dijkstra, A* (dengan heuristik Euclidean/Haversine murni), dan Floyd-Warshall gagal memenuhi parameter batas waktu dan memori untuk skala operasional tersebut!
  2. Lakukan perbandingan arsitektural antara pendekatan hierarkis berbasis *Contraction Hierarchies* (CH) vs. *Hub Labeling* (HL) vs. *Customizable Contraction Hierarchies* (CCH). Tentukan metode yang paling optimal jika profil bobot jalan berubah dinamis sesuai pola kemacetan lalu lintas setiap jam!

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Real-Time Dynamic Failure Recovery Routing Engine
Rancang dan implementasikan mesin perutean (*routing engine*) dalam memori (*in-memory*) berkinerja tinggi yang mampu menangani kegagalan infrastruktur fisik secara adaptif.

#### Problem Statement
Anda mengelola infrastruktur jaringan tulang punggung (*backbone network*) yang terdiri dari sejumlah simpul jaringan (*routers/switches*) dan kabel serat optik. Sistem harus secara konsisten melayani kueri jalur dengan latensi minimum seraya secara instan mendeteksi jika sebuah jalur fisik putus, mengisolasi komponen yang terputus, dan merutekan ulang lalu lintas tanpa menunda paket data.

#### Requirements
1. **Core Graph Representation:** Implementasikan struktur graf terarah dengan representasi hemat memori yang optimal untuk *traversal* (misal: *Compressed Sparse Row* / CSR yang dimutasi via *adjacency list indirection*).
2. **Shortest Path Engine:** Implementasikan algoritma perutean dengan kompleksitas waktu sub-linear terhadap ukuran graf global untuk kueri berulang (disarankan menggunakan *Bi-directional Dijkstra* yang dipercepat dengan struktur heap terindeks).
3. **Dynamic Topology Mutation (Link Failure):**
   * Dukung operasi `disable_edge(u, v)` dan `update_weight(u, v, w)` secara efisien.
   * Gunakan DSU dengan fungsionalitas *Rollback* atau *Dynamic Connectivity* (Euler Tour Tree / Link-Cut Tree dasar) untuk mengecek secara instan ($\mathcal{O}(1)$ atau $\mathcal{O}(\log V)$) apakah dua simpul masih berada dalam satu komponen yang terhubung sebelum menjalankan pencarian rute.
4. **Negative Cycle & Anomaly Protection:** Integrasikan modul sanitasi berbasis Bellman-Ford/SPFA parsial yang mampu memvalidasi bahwa metrik latensi yang diinjeksikan secara dinamis tidak membentuk anomali sink latensi negatif (*negative cycle loop*).

#### Constraints
* Jumlah Simpul: $|V| \le 50.000$
* Jumlah Sisi Awal: $|E| \le 500.000$
* Waktu Eksekusi Kueri Jalur: $\le 5\text{ ms}$ untuk setiap pemanggilan pencarian rute terpendek.
* Waktu Penanganan Mutasi Sisi: $\le 1\text{ ms}$ untuk mematikan sisi dan memvalidasi konektivitas komponen.
* Batas Alokasi Memori Tambahan: Maksimum $256\text{ MB}$ untuk keseluruhan struktur data graf dan indeks.

#### Expected Output
1. Modul kode modular yang memisahkan abstraksi Graf, Priority Queue/Heap, Disjoint Set Engine, dan Routing Service.
2. Hasil cetak eksekusi (*benchmark log*) yang menampilkan:
   * Waktu inisialisasi graf.
   * Latensi kalkulasi rute awal sebelum terjadi gangguan.
   * Latensi saat mutasi pemutusan 5% sisi penting (*critical bridge links*).
   * Verifikasi rute alternatif baru yang dihasilkan pasca-kegagalan.
   * Pengujian pencegahan kegagalan (*graceful rejection*) ketika kueri diarahkan ke simpul yang telah terisolasi total secara topologis.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan matematis dari pendekatan greedy pada Dijkstra dan bukti mengapa edge berbobot negatif merusak properti optimalitas lokal.
- [ ] Relasi recurrence pada Floyd-Warshall dan justifikasi matematis penghapusan dimensi k tanpa menimbulkan *race-condition* nilai status pada array 2D.
- [ ] Mekanisme formal di balik *Cut Property* dan *Cycle Property* sebagai penjamin kebenaran pada pembentukan Spanning Tree.
- [ ] Bukti analitis keterbatasan iterasi $(|V|-1)$ pada Bellman-Ford untuk deteksi siklus negatif pada graf berarah.
- [ ] Peran fungsi inversi Ackermann $\alpha(n)$ dalam mengikat kompleksitas waktu amortisasi operasi DSU secara teoretis.
- [ ] Mekanisme deteksi bottleneck relaksasi saat menggunakan *Lazy Heap Deletion* vs *Indexed Min-Heap* pada algoritma pencarian jalur.
- [ ] Konsekuensi struktural implementasi *Path Compression* dalam struktur data persisten dan konkurensi multi-threaded.

### Saya tidak perlu menghafal:
- [ ] Penurunan matematis penuh dari pembuktian batas atas fungsi Ackermann non-primitif rekursif tingkat tinggi.
- [ ] Sintaks spesifik pustaka pihak ketiga untuk algoritma graf (misal: antarmuka internal Boost Graph Library, NetworkX, atau Guava Graph).
- [ ] Konstanta presisi pengali waktu eksekusi tingkat rendah untuk varian heuristik graf khusus yang terikat pada mikroarsitektur prosesor tertentu.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan algoritma Dijkstra dari awal menggunakan *Indexed Priority Queue* dengan fungsionalitas `decrease-key` eksplisit yang teroptimasi.
- [ ] Membangun struktur data Disjoint Set Union (DSU) yang dilengkapi teknik *Path Compression* dan *Union by Rank/Size* secara nir-cacat.
- [ ] Mengimplementasikan algoritma Kruskal dan Prim dari awal serta menentukan pemilihan algoritma yang tepat berdasarkan tingkat kepadatan (*density*) graf target.
- [ ] Mengonstruksi algoritma Bellman-Ford yang mampu mengekstraksi dan mencetak seluruh simpul yang terlibat dalam *negative weight cycle*.
- [ ] Mendiagnosis dan memperbaiki masalah *infinite loop* atau degradasi performa pada modifikasi graf berbobot dinamis di sistem berskala produksi.
- [ ] Menghitung kebutuhan memori teoritis dan riil dari representasi graf (*Adjacency List*, *Adjacency Matrix*, *Forward Star / CSR*) untuk mencegah kegagalan alokasi memori (*Out Of Memory*).