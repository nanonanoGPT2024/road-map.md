# BAB 07: Quiz, Challenge, & Knowledge Check
**Bab 07: Pohon Biner, Binary Search Tree (BST), & Algoritma Traversal**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Invariant Binary Search Tree (BST) dan Dampak Strukturalnya
Jelaskan secara formal *invariant* matematika dari sebuah Binary Search Tree (BST). Bagaimana *invariant* ini membedakan BST dari Binary Tree biasa, dan mengapa properti tersebut memungkinkan algoritma pencarian mencapai kompleksitas waktu rata-rata $\mathcal{O}(\log N)$? Analisis pula skenario di mana kompleksitas waktu pencarian tersebut terdegradasi menjadi $\mathcal{O}(N)$.

### Soal 1.2: Tipologi Pohon Biner: Full, Complete, dan Perfect
Bedakan secara presisi definisi struktural dari *Full Binary Tree*, *Complete Binary Tree*, dan *Perfect Binary Tree*. Berikan analisis matematis mengenai hubungan antara tinggi pohon ($h$) dan jumlah node ($N$) pada masing-masing tipe, serta jelaskan mengapa representasi array implisit (tanpa pointer eksplisit) sangat optimal untuk *Complete Binary Tree* tetapi sangat boros memori (*sparse*) untuk *Degenerate Tree*.

### Soal 1.3: Kompleksitas Ruang Traversal: DFS vs. BFS
Bandingkan karakteristik penggunaan memori (*auxiliary space complexity*) antara *Depth-First Search* (Pre-order, In-order, Post-order) yang memanfaatkan *call stack* (atau stack eksplisit) dengan *Breadth-First Search* / *Level-Order Traversal* yang memanfaatkan *queue*. Tentukan dalam topologi pohon seperti apa (misal: *skewed* vs. *balanced/bushy*) masing-masing algoritma mencapai skenario penggunaan memori terburuk (*worst-case memory footprint*).

### Soal 1.4: Mekanisme Deletion pada BST: Kasus Dua Anak (*Two Children*)
Saat menghapus sebuah node pada BST yang memiliki dua *child node*, mengapa node tersebut harus digantikan oleh *In-order Predecessor* atau *In-order Successor*? Jelaskan langkah-langkah mutasi pointer/nilai yang terjadi, bagaimana invariant BST tetap terjaga pasca-penghapusan, dan buktikan bahwa node pengganti (*successor/predecessor*) dijamin memiliki maksimal satu anak.

### Soal 1.5: Rekonstruksi Pohon Biner dari Array Traversal
Mengapa representasi traversal *In-order* saja tidak cukup untuk merekonstruksi topologi *Binary Tree* secara deterministik? Kombinasi traversal apa yang secara mutlak diperlukan untuk membangun kembali pohon biner secara unik (*unique tree reconstruction*)? Jelaskan peran struktural elemen pertama pada *Pre-order* atau elemen terakhir pada *Post-order* dalam mempartisi array *In-order*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Algoritma Morris Traversal dan Eliminasi Call Stack
Algoritma traversal standar membutuhkan memori $\mathcal{O}(h)$ untuk tracking traversal path. Jelaskan cara kerja **Morris In-Order Traversal** yang mampu mereduksi kompleksitas ruang bantu menjadi $\mathcal{O}(1)$. Bagaimana algoritma ini memanfaatkan *null pointer* pada node daun (*leaf nodes*) untuk membentuk *temporary threaded binary tree*, dan bagaimana mekanisme pemulihan struktur asli pohon sebelum fungsi traversal mengembalikan hasil akhir?

### Soal 2.2: Root Cause Analysis: Stack Overflow pada Rekursi Dalam
Sebuah layanan backend mengalami *crash* mendadak dengan sinyal `SIGSEGV` (Segmentation Fault) akibat *Call Stack Overflow* ketika mengeksekusi traversal rekursif traversal in-order pada BST dengan 500.000 node. 
```text
Traceback:
  at traverse(node.left)
  at traverse(node.left)
  ... [10,000 frames omitted]
Segmentation fault (core dumped)
```
1. Diagnosis mengapa optimasi compiler *Tail-Call Optimization* (TCO) umumnya gagal diterapkan pada fungsi in-order traversal rekursif ganda (`traverse(node.left); process(node); traverse(node.right);`).
2. Tuliskan pseudocode/solusi arsitektural untuk mentransformasikan fungsi rekursif tersebut menjadi pendekatan iteratif berbasis heap-allocated dynamic stack guna mencegah limitasi *thread execution stack*.

### Soal 2.3: Pitfall Validasi BST (Range Bounds vs. Local Subtree Check)
Perhatikan implementasi validasi BST berikut yang mengandung bug laten:
```cpp
bool isValidBST(TreeNode* root) {
    if (root == nullptr) return true;
    if (root->left != nullptr && root->left->val >= root->val) return false;
    if (root->right != nullptr && root->right->val <= root->val) return false;
    return isValidBST(root->left) && isValidBST(root->right);
}
```
1. Berikan contoh kasus uji (pohon biner minimal 3 node) di mana fungsi di atas mengembalikan `true` secara keliru (*false positive*).
2. Bagaimana perbaikan algoritma yang benar menggunakan propagasi batas rentang nilai minimum dan maksimum $(\text{low}, \text{high})$, dan bagaimana menangani potensi *integer underflow/overflow* jika nilai node bernilai `INT_MIN` atau `INT_MAX`?

### Soal 2.4: Bottleneck Cache Locality pada Pointer-Chasing Traversal
Dalam arsitektur CPU modern, mengakses node pohon biner melalui *pointer indirection* (`node->left`, `node->right`) sering kali memicu *CPU Cache Miss* (L1/L2/L3 miss) secara masif dibandingkan melakukan iterasi pada array datar (*contiguous array*). Analisis secara arsitektural mengapa traversal BST standar memiliki performa *Instructions Per Cycle* (IPC) yang rendah, dan bagaimana teknik transformasi layout data seperti *van Emde Boas layout* atau pemadatan node ke dalam blok *B-Tree-like array* dapat memitigasi masalah *hardware prefetching* ini.

### Soal 2.5: Race Condition pada Concurrency BST (Hand-Over-Hand Locking)
Dalam skenario *multi-threaded*, dua thread melakukan mutasi secara paralel pada node yang saling berdekatan dalam sebuah BST tanpa sinkronisasi global. Jelaskan mengapa mengunci seluruh pohon menggunakan satu *coarse-grained lock* (seperti `std::mutex`) menghancurkan throughput sistem. Selanjutnya, paparkan mekanisme kerja **Hand-Over-Hand Locking** (atau *crabbing lock*) saat melakukan traversal dan mutasi pada node, serta sebutkan risiko *deadlock* jika struktur traversal membutuhkan traversing balik (*parent pointer reference*).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Latensi Index In-Memory akibat Data Terurut (Sequential Insertion)
* **Konteks:** Sebuah microservice ingest telemetri IoT memelihara in-memory index berbasis Binary Search Tree polos (*plain BST*) untuk mencatat `timestamp` pesan guna memproses query rentang (*range query*).
* **Insiden:** Ketika service di-restart, data historis dipulihkan (*replay*) dari event log Apache Kafka secara berurutan (*strictly ascending order* berdasarkan `timestamp`). Tak lama setelah restart, CPU usage melonjak hingga 100%, p99 latency pencarian melonjak dari 20 mikrodetik menjadi 450 milidetik, dan throughput service anjlok drastis.
* **Pertanyaan Diagnostik:**
  1. Identifikasi perubahan topologi pohon yang terjadi akibat *insertion pattern* tersebut dan analisis perubahan kompleksitas waktu operasinya dari sisi *Big-O*.
  2. Jelaskan mengapa *garbage collection* (pada bahasa managed seperti Java/Go) atau *allocator fragmentation* (pada C/C++) dapat memperburuk kondisi insiden ini saat ukuran pohon mencapai jutaan node.
  3. Berikan proposal mitigasi jangka pendek (tanpa mengubah struktur data BST dasar pada proses read) dan solusi arsitektural jangka panjang untuk mencegah masalah ini secara permanen.

### Skenario B: Broken Subtree References pada Concurrent High-Frequency Update
* **Konteks:** Sebuah platform e-commerce menggunakan struktur pohon hierarkis berbasis pointer memory untuk merepresentasikan katalog kategori produk. Karena query katalog sangat sering dibaca (*read-heavy*), tim engineering menerapkan *Read-Write Lock* (`std::shared_mutex` atau `sync.RWMutex`) per-node untuk memaksimalkan konkurensi alih-alih meletakkan lock pada root.
* **Insiden:** Selama event diskon kilat (*flash sale*), Thread-A melakukan operasi mutasi berupa *pruning* (penghapusan) Subtree Kategori $X$ dari parent node $P$. Bersamaan dengan itu, Thread-B sedang menelusuri subtree di bawah $X$ untuk membaca atribut produk $Y$. Sistem mengalami *panic* / *crash* fatal dengan error *Null Pointer Dereference* atau membaca data *corrupted* (akses memori yang sudah di-*free* / *use-after-free*).
* **Pertanyaan Diagnostik:**
  1. Rekonstruksi urutan eksekusi (*interleaving sequence*) antara Thread-A dan Thread-B yang memicu akses memori ilegal tersebut meskipun masing-masing node dilindungi *node-level mutex*.
  2. Mengapa skema *locking down the tree* (mengunci child sebelum melepas parent lock) sulit melindungi pembacaan jika ada proses *re-parenting* atau *node promotion* saat penghapusan?
  3. Evaluasi pendekatan arsitektur alternatif untuk skenario ini: Implementasikan pola *Copy-On-Write* (COW Tree) atau gunakan paradigma *Epoch-Based Reclamation* (EBR) / RCU (*Read-Copy-Update*). Bagaimana trade-off memori dan performa dari solusi yang Anda rekomendasikan?

### Skenario C: Trade-off Arsitektur: IP Route Matching Gateway (BST vs. Prefix Tree/Trie)
* **Konteks:** Anda diminta mendesain *In-Memory Routing Engine* untuk sebuah API Gateway berkecepatan tinggi yang harus memetakan alamat IP masuk (IPv4) ke upstream service IDs yang sesuai berdasarkan aturan subnet CIDR (misal: `192.168.1.0/24` $\to$ Service-A, `192.168.0.0/16` $\to$ Service-B). Gateway ini menangani 500.000 requests per detik (RPS) dengan SLA latensi lookup sub-mikrodetik.
* **Dilema Arsitektur:** Tim internal terbelah antara dua pendekatan:
  * **Opsi 1:** Mengonversi rentang IP CIDR menjadi range numerik 32-bit integer dan menyimpannya di dalam Binary Search Tree (atau variasinya: Augmented Interval BST).
  * **Opsi 2:** Menggunakan Bitwise Trie (Radix Tree/Prefix Tree) dengan kedalaman maksimal 32 level.
* **Pertanyaan Diagnostik:**
  1. Analisis *lookup complexity* dan efisiensi *longest-prefix match* antara Augmented Interval BST vs. Radix Tree untuk kasus IPv4 (32-bit).
  2. Bagaimana karakteristik penggunaan memori (*memory overhead* per pointer) dari kedua pendekatan tersebut ketika menangani 1.000.000 aturan routing yang heterogen?
  3. Buat keputusan teknis yang justified: Opsi mana yang Anda pilih untuk lingkungan produksi API Gateway tersebut? Sertakan argumen terkait *hardware cache locality*, prediktabilitas latensi (*jitter*), dan kompleksitas konkurensi (update routing table tanpa downtime).

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Thread-Safe BST In-Memory Indexer dengan Garbage-Collected Tombstone & Iterative Range Query Engine

#### Problem Statement
Rancang dan implementasikan sebuah *in-memory key-value indexing component* berbasis Binary Search Tree yang dirancang untuk performa tinggi, thread-safe, dan bebas dari risiko rekursi stack overflow. Modul ini akan digunakan sebagai mesin index lokal untuk sebuah storage engine mini.

#### Requirements
1. **Iterative Core Operations:** Seluruh operasi fundamental (`Insert`, `Search`, `Delete`, `RangeQuery`) **wajib** diimplementasikan secara **iteratif**. Dilarang keras menggunakan panggilan rekursif untuk mencegah konsumsi *thread call stack*.
2. **Deletion via Tombstone & Structural Purge:**
   * Operasi `Delete` tahap pertama harus menggunakan penandaan logis (*Logical Deletion*) menggunakan flag `is_deleted = true` (Tombstone pattern) guna meminimalkan latency blocking.
   * Modul harus menyediakan fungsi maintenance: `PurgeDeletedNodes()`, yang berjalan secara background/eksplisit untuk melakukan restrukturisasi pointer BST secara fisik, membuang semua node bertanda tombstone tanpa melanggar *invariant* BST.
3. **Range Query Engine:**
   * Menyediakan fungsi `SearchRange(Key low, Key high)` yang mengembalikan semua pasangan key-value yang berada di dalam rentang rentang inklusif `[low, high]` secara terurut menaik (*ascending order*).
   * Engine traversal harus langsung melakukan *pruning* subtree yang berada di luar rentang (tidak boleh menelusuri subtree kiri jika nilai node saat ini sudah lebih kecil dari `low`).
4. **Concurrency Safety:** Implementasikan skema thread-safety yang efisien untuk multi-reader dan multi-writer menggunakan mekanisme sinkronisasi yang terukur (bisa berbasis Fine-Grained Locking per node atau Synchronized Root Reader-Writer Lock).

#### Constraints
* **Language Agnostic:** C++ (standar C++17/C++20), Rust, Go, atau Java.
* **No Recursive Functions:** 0 panggilan fungsi rekursif di seluruh codebase BST engine.
* **Auxiliary Space:** Maksimal $\mathcal{O}(h)$ auxiliary space pada operasi range query menggunakan manual stack berbasis heap.
* **Memory Management:** Tidak boleh ada memory leak (wajib membersihkan resource heap secara deterministik saat node di-purge atau instance tree di-destruct).

#### Expected Output
1. Source code implementasi lengkap yang modular (Node struct/class, Tree class/struct, Driver Program).
2. Unit Test terautomasi yang menguji skenario:
   * Penyisipan 10.000 data sequential (verifikasi tidak terjadi stack overflow).
   * Operasi logical deletion dengan tombstone dilanjutkan dengan structural purge.
   * Eksekusi `SearchRange` yang memverifikasi bahwa subtree di luar jangkauan di-prune dengan benar dan hasil terurut deterministik.
   * Skenario multi-threaded read/write untuk memverifikasi konsistensi invariant BST (tidak terjadi race condition atau segfault).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan matematis formal antara General Binary Tree, Binary Search Tree (BST), Full, Complete, dan Perfect Binary Tree.
- [ ] Invariant fundamental BST: $\forall x \in \text{LeftSubtree}(Node), x.key < Node.key$ dan $\forall y \in \text{RightSubtree}(Node), y.key > Node.key$.
- [ ] Kompleksitas asimptotik rata-rata vs terburuk ($\mathcal{O}(\log N)$ vs $\mathcal{O}(N)$) untuk operasi search, insert, dan delete pada un-balanced BST.
- [ ] Mekanisme in-order successor dan in-order predecessor pada proses restrukturisasi node 2-anak saat deletion.
- [ ] Perbedaan pola traversal DFS (Pre-order, In-order, Post-order) serta representasi BFS (Level-order).
- [ ] Batasan memori thread call stack sistem operasi dan implikasinya terhadap fungsi rekursif traversal pada deep/skewed trees.
- [ ] Karakteristik Morris Traversal dalam memanfaatkan temporary threading pointer daun untuk memori $\mathcal{O}(1)$.
- [ ] Pola penelusuran validitas BST berbasis rentang $(\text{low}, \text{high})$ dinamis untuk mencegah bug pemeriksaan lokal (*local subtree trap*).

### Saya tidak perlu menghafal:
- [ ] Sintaks spesifik implementasi Morris traversal pada bahasa pemrograman tertentu di luar algoritma konseptualnya.
- [ ] Nilai eksak floating-point konstan logaritma konversi tinggi pohon biner.
- [ ] Implementasi boilerplate pointer-swapping mikro yang dapat diturunkan kembali menggunakan diagram state memori.

### Saya harus bisa melakukan:
- [ ] Mengonversi fungsi tree traversal rekursif menjadi bentuk iteratif penuh menggunakan heap-allocated stack tanpa risiko *call stack overflow*.
- [ ] Menganalisis kondisi memory leak atau *dangling pointer* saat melakukan mutasi struktural subtree pada bahasa unmanaged (C/C++).
- [ ] Mengimplementasikan algoritma validasi BST yang robust terhadap nilai boundary tipe data primitif (`INT_MIN`, `INT_MAX`).
- [ ] Menerapkan optimasi pruning pada operasi range query BST agar tidak mengunjungi node di luar batas interval `[low, high]`.
- [ ] Mendiagnosis degradasi performa pohon biner akibat data insertion yang terurut secara sequential pada environment produksi.