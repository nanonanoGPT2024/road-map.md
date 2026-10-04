# Data Structures & Algorithms (DSA)
## Silabus Lengkap — Standar GEMINI.md

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 KODE KURSUS : GEMINI-DSA-001
 VERSI       : 2.1.0
 STANDAR     : roadmap.sh/datastructures-and-algorithms
 BAHASA      : Indonesia Profesional Teknis
 TINGKAT     : Intermediate → Advanced
 DURASI      : 20 Minggu (240 Jam Efektif)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📋 Daftar Isi

| # | Bagian | Deskripsi |
|---|--------|-----------|
| 1 | [Course Overview & Mindset](#1-course-overview--mindset) | Filosofi, tujuan, dan prasyarat kursus |
| 2 | [Learning Roadmap](#2-learning-roadmap-diagram-pohon-ascii) | Diagram pohon 10 BAB lengkap |
| 3 | [Navigasi Detail Bab 01–10](#3-navigasi-detail-bab-01-s-bab-10) | Modul per bab dengan link relatif |
| 4 | [Capstone Project Enterprise](#4-spesifikasi-capstone-project-enterprise) | Spesifikasi proyek akhir kursus |
| 5 | [Penilaian & Sertifikasi](#5-penilaian--sertifikasi) | Rubrik dan jalur sertifikasi |
| 6 | [Referensi & Sumber Daya](#6-referensi--sumber-daya) | Pustaka, tools, dan komunitas |

---

## 1. Course Overview & Mindset

### 1.1 Filosofi Kursus

> *"Algoritma bukan sekadar kode — ia adalah cara berpikir terstruktur untuk menyelesaikan masalah kompleks dengan elegan dan efisien."*

Kursus ini dirancang berdasarkan prinsip **"Understand → Implement → Optimize → Apply"**. Setiap konsep tidak hanya diajarkan secara teoritis, tetapi langsung dikontekstualisasikan dalam skenario industri nyata — mulai dari sistem rekomendasi e-commerce, routing jaringan telekomunikasi, hingga mesin pencari skala enterprise.

### 1.2 Mengapa DSA Kritis di Era Modern?

```
┌─────────────────────────────────────────────────────────────────┐
│  REALITAS INDUSTRI TEKNOLOGI 2024                               │
├─────────────────────────────────────────────────────────────────┤
│  ✦ 95% perusahaan teknologi tier-1 (FAANG, unicorn startup)    │
│    menggunakan DSA sebagai filter utama rekrutmen teknis        │
│                                                                 │
│  ✦ Sistem dengan algoritma optimal dapat mengurangi biaya       │
│    komputasi cloud hingga 60-80% dibanding implementasi naif    │
│                                                                 │
│  ✦ AI/ML modern (LLM, Graph Neural Network) dibangun di atas   │
│    fondasi struktur data graf, pohon, dan matriks sparse        │
│                                                                 │
│  ✦ Pemahaman DSA mendalam membedakan Software Engineer biasa   │
│    dengan Principal/Staff Engineer yang merancang sistem        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Tujuan Pembelajaran Utama (Learning Outcomes)

Setelah menyelesaikan kursus ini, peserta mampu:

- **[LO-01]** Menganalisis kompleksitas waktu dan ruang algoritma menggunakan notasi Big-O, Big-Θ, dan Big-Ω secara akurat
- **[LO-02]** Mengimplementasikan seluruh struktur data fundamental (linear, non-linear, hash-based) dari nol tanpa library bawaan
- **[LO-03]** Memilih dan menerapkan paradigma algoritma yang tepat (Divide & Conquer, Dynamic Programming, Greedy, Backtracking) untuk kategori masalah tertentu
- **[LO-04]** Merancang solusi algoritma untuk masalah graf kompleks termasuk shortest path, MST, dan network flow
- **[LO-05]** Mengoptimalkan performa sistem nyata menggunakan teknik advanced (cache-aware algorithms, probabilistic data structures)
- **[LO-06]** Membangun dan mendeploy sistem enterprise yang menggabungkan multiple algoritma dalam arsitektur terdistribusi

### 1.4 Prasyarat Kursus

```
WAJIB (Hard Prerequisites):
  ├── Pemrograman prosedural/OOP minimal 1 bahasa (Python/Java/C++/Go)
  ├── Matematika diskrit dasar (logika, himpunan, fungsi)
  └── Pemahaman dasar rekursi dan fungsi

DIREKOMENDASIKAN (Soft Prerequisites):
  ├── Pengalaman mengerjakan proyek software minimal 3 bulan
  ├── Familiar dengan Git dan version control
  └── Dasar-dasar sistem operasi (memory, proses)
```

### 1.5 Mindset Framework: The DSA Thinking Model

```
╔══════════════════════════════════════════════════════════════════╗
║              THE GEMINI DSA THINKING MODEL                      ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║   STEP 1: UNDERSTAND    →  Pahami masalah, bukan langsung kode  ║
║   STEP 2: ABSTRACT      →  Identifikasi pola & struktur data    ║
║   STEP 3: BRUTE FORCE   →  Solusi naif dulu, pastikan benar     ║
║   STEP 4: OPTIMIZE      →  Analisis bottleneck, terapkan teknik ║
║   STEP 5: VERIFY        →  Edge cases, stress test, proof       ║
║   STEP 6: COMMUNICATE   →  Jelaskan trade-off ke tim            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

### 1.6 Bahasa Pemrograman & Tools

| Kategori | Tools | Keterangan |
|----------|-------|------------|
| **Bahasa Utama** | Python 3.11+ | Pseudocode-like, rapid prototyping |
| **Bahasa Sekunder** | Java 21 / C++ 20 | Performa kritis, interview standard |
| **Visualisasi** | VisuAlgo, Algorithm Visualizer | Pemahaman visual |
| **Profiling** | cProfile, Valgrind, perf | Analisis performa nyata |
| **Testing** | pytest, JUnit 5 | Unit & stress testing |
| **Kolaborasi** | GitHub, LeetCode, HackerRank | Portfolio & latihan |

---

## 2. Learning Roadmap (Diagram Pohon ASCII)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    ROADMAP DSA — GEMINI-DSA-001
                    ════════════════════════════
                    [FONDASI] → [STRUKTUR] → [ALGORITMA] → [ADVANCED] → [ENTERPRISE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 ROOT: DATA STRUCTURES & ALGORITHMS (DSA)
 │
 ├─── FASE 1: FONDASI MATEMATIS & ANALISIS (Minggu 1-4)
 │    │
 │    ├─── BAB 01: Kompleksitas & Analisis Algoritma ──────────── [Minggu 1-2]
 │    │    ├── Modul 01.1: Notasi Asimtotik & Big-O Analysis
 │    │    ├── Modul 01.2: Analisis Rekursi & Master Theorem
 │    │    └── Modul 01.3: Space Complexity & Trade-off Analysis
 │    │
 │    └─── BAB 02: Struktur Data Linear ──────────────────────── [Minggu 3-4]
 │         ├── Modul 02.1: Array, String & Buffer Management
 │         ├── Modul 02.2: Linked List (Singly, Doubly, Circular)
 │         └── Modul 02.3: Stack, Queue & Deque
 │
 ├─── FASE 2: STRUKTUR DATA NON-LINEAR (Minggu 5-8)
 │    │
 │    ├─── BAB 03: Pohon & Struktur Hierarkis ────────────────── [Minggu 5-6]
 │    │    ├── Modul 03.1: Binary Tree & Binary Search Tree (BST)
 │    │    ├── Modul 03.2: Balanced Trees (AVL, Red-Black Tree)
 │    │    └── Modul 03.3: Heap, Priority Queue & Trie
 │    │
 │    └─── BAB 04: Hashing & Struktur Data Probabilistik ──────── [Minggu 7-8]
 │         ├── Modul 04.1: Hash Table — Desain & Collision Resolution
 │         ├── Modul 04.2: Bloom Filter, Count-Min Sketch & HyperLogLog
 │         └── Modul 04.3: Consistent Hashing & Distributed Hash Table
 │
 ├─── FASE 3: ALGORITMA FUNDAMENTAL (Minggu 9-12)
 │    │
 │    ├─── BAB 05: Algoritma Pengurutan & Pencarian ───────────── [Minggu 9-10]
 │    │    ├── Modul 05.1: Sorting Klasik (Merge, Quick, Heap Sort)
 │    │    ├── Modul 05.2: Linear Sorting & External Sort
 │    │    └── Modul 05.3: Binary Search & Variasi Lanjutan
 │    │
 │    └─── BAB 06: Graf & Algoritma Traversal ────────────────── [Minggu 11-12]
 │         ├── Modul 06.1: Representasi Graf & BFS/DFS
 │         ├── Modul 06.2: Shortest Path (Dijkstra, Bellman-Ford, Floyd-Warshall)
 │         └── Modul 06.3: MST, Topological Sort & Strongly Connected Components
 │
 ├─── FASE 4: PARADIGMA ALGORITMA LANJUTAN (Minggu 13-16)
 │    │
 │    ├─── BAB 07: Divide & Conquer + Greedy ─────────────────── [Minggu 13-14]
 │    │    ├── Modul 07.1: Divide & Conquer — Paradigma & Aplikasi
 │    │    ├── Modul 07.2: Greedy Algorithm — Correctness Proof
 │    │    └── Modul 07.3: Interval Scheduling, Huffman & Kruskal
 │    │
 │    └─── BAB 08: Dynamic Programming ───────────────────────── [Minggu 15-16]
 │         ├── Modul 08.1: DP Fundamentals — Memoization & Tabulation
 │         ├── Modul 08.2: DP Klasik (Knapsack, LCS, LIS, Edit Distance)
 │         └── Modul 08.3: DP Lanjutan (Bitmask DP, DP on Trees/Graphs)
 │
 └─── FASE 5: TOPIK ADVANCED & ENTERPRISE (Minggu 17-20)
      │
      ├─── BAB 09: Algoritma String & Komputasi Geometri ──────── [Minggu 17-18]
      │    ├── Modul 09.1: String Matching (KMP, Rabin-Karp, Aho-Corasick)
      │    ├── Modul 09.2: Suffix Array, Suffix Tree & Z-Algorithm
      │    └── Modul 09.3: Computational Geometry — Convex Hull & Line Sweep
      │
      └─── BAB 10: Algoritma Advanced & Sistem Terdistribusi ──── [Minggu 19-20]
           ├── Modul 10.1: Network Flow, Matching & Linear Programming
           ├── Modul 10.2: Randomized Algorithms & Approximation
           └── Modul 10.3: DSA dalam Sistem Terdistribusi & Cloud

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CAPSTONE PROJECT ENTERPRISE ──────────────────────────────────── [Minggu 20]
  "Distributed Search & Recommendation Engine"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEGENDA TINGKAT KESULITAN:
  ◆ Fundamental   ◈ Intermediate   ◉ Advanced   ★ Expert
  BAB 01-02: ◆    BAB 03-04: ◈    BAB 05-06: ◈◉   BAB 07-08: ◉   BAB 09-10: ★
```

---

## 3. Navigasi Detail Bab 01 s/d Bab 10

---

### 📦 BAB 01 — Kompleksitas & Analisis Algoritma

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 01: Kompleksitas & Analisis Algoritma                                  │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◆ Fundamental                        │
│  Prasyarat: Matematika dasar, pemrograman prosedural                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Fondasi mutlak sebelum mempelajari algoritma apapun. Bab ini membangun kemampuan analitis untuk mengukur, membandingkan, dan memprediksi performa algoritma secara matematis — keterampilan yang membedakan engineer yang *menulis kode* dengan engineer yang *merancang sistem*.

**Kompetensi yang Dicapai:**
- Menghitung kompleksitas waktu dan ruang untuk algoritma iteratif dan rekursif
- Membuktikan batas atas dan bawah kompleksitas menggunakan definisi formal
- Mengaplikasikan Master Theorem untuk menyelesaikan relasi rekurensi

---

#### 📄 [Modul 01.1 — Notasi Asimtotik & Big-O Analysis](./bab-01/modul-01-1-notasi-asimtotik.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam (4 sesi × 2 jam) |
| **Format** | Teori + Latihan Analisis + Kuis |
| **Tools** | Python profiler, Desmos graphing |

**Topik Utama:**
```
1.1.1  Definisi Formal Big-O, Big-Ω, Big-Θ
        ├── Limit definition: lim f(n)/g(n)
        ├── Konstanta dan faktor dominan
        └── Pembuktian formal dengan ε-δ

1.1.2  Hierarki Kompleksitas
        ├── O(1) → O(log n) → O(n) → O(n log n) → O(n²) → O(2ⁿ) → O(n!)
        ├── Visualisasi pertumbuhan fungsi
        └── Implikasi praktis pada dataset besar

1.1.3  Analisis Kasus (Best, Average, Worst)
        ├── Amortized analysis — aggregate, accounting, potential method
        ├── Contoh: Dynamic Array (ArrayList) amortized O(1) push
        └── Probabilistic analysis — expected case

1.1.4  Analisis Kode Nyata
        ├── Loop tunggal, nested loop, loop dengan break
        ├── Fungsi rekursif sederhana
        └── Latihan: Analisis 20 snippet kode industri
```

**Latihan Praktis:**
- [ ] Analisis kompleksitas 15 fungsi Python yang diberikan
- [ ] Implementasi benchmark empiris vs analisis teoritis
- [ ] Kuis: Urutkan 10 algoritma berdasarkan kompleksitas

---

#### 📄 [Modul 01.2 — Analisis Rekursi & Master Theorem](./bab-01/modul-01-2-rekursi-master-theorem.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam (4 sesi × 2 jam) |
| **Format** | Teori + Problem Set + Lab |
| **Tools** | Recursion tree visualizer |

**Topik Utama:**
```
1.2.1  Relasi Rekurensi
        ├── Definisi dan cara membaca relasi rekurensi
        ├── Metode substitusi (unrolling)
        └── Metode pohon rekursi (recursion tree)

1.2.2  Master Theorem
        ├── Tiga kasus Master Theorem dengan bukti intuitif
        ├── T(n) = aT(n/b) + f(n) — identifikasi a, b, f(n)
        ├── Kasus 1: f(n) = O(n^(log_b(a) - ε))
        ├── Kasus 2: f(n) = Θ(n^log_b(a))
        ├── Kasus 3: f(n) = Ω(n^(log_b(a) + ε))
        └── Limitasi Master Theorem & Akra-Bazzi Method

1.2.3  Analisis Rekursi Lanjutan
        ├── Rekursi dengan multiple subproblem berbeda ukuran
        ├── Tail recursion dan optimasi compiler
        └── Konversi rekursi ke iterasi (stack-based)

1.2.4  Studi Kasus Industri
        ├── Merge Sort: T(n) = 2T(n/2) + O(n)
        ├── Binary Search: T(n) = T(n/2) + O(1)
        └── Strassen Matrix Multiply: T(n) = 7T(n/2) + O(n²)
```

**Lab Assignment:**
- [ ] Selesaikan 10 relasi rekurensi menggunakan 3 metode berbeda
- [ ] Implementasi dan verifikasi empiris Master Theorem pada 5 algoritma

---

#### 📄 [Modul 01.3 — Space Complexity & Trade-off Analysis](./bab-01/modul-01-3-space-complexity-tradeoff.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam (4 sesi × 2 jam) |
| **Format** | Teori + Case Study + Mini Project |
| **Tools** | memory_profiler, Valgrind |

**Topik Utama:**
```
1.3.1  Space Complexity Analysis
        ├── Auxiliary space vs total space
        ├── Stack space dalam rekursi
        ├── In-place algorithms (O(1) space)
        └── Analisis space untuk struktur data dinamis

1.3.2  Time-Space Trade-off
        ├── Memoization sebagai time-space trade-off
        ├── Lookup table vs komputasi ulang
        ├── Compression algorithms trade-off
        └── Cache-aware programming dasar

1.3.3  Practical Performance Analysis
        ├── Profiling tools dan interpretasi hasil
        ├── Benchmarking metodologi yang benar
        ├── Constant factors dalam praktik (cache miss, branch prediction)
        └── Asymptotic vs real-world performance gap

1.3.4  Mini Project: Algorithm Profiler
        └── Bangun tool sederhana yang mengukur time & space
            secara otomatis untuk fungsi Python apapun
```

**Deliverable Bab 01:**
> 📝 **Laporan Analisis:** Analisis kompleksitas lengkap (time + space) untuk 5 algoritma sorting berbeda, disertai benchmark empiris dan visualisasi perbandingan.

---

### 📦 BAB 02 — Struktur Data Linear

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 02: Struktur Data Linear                                               │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◆ Fundamental                        │
│  Prasyarat: BAB 01 selesai, OOP dasar                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Struktur data linear adalah blok bangunan dasar semua sistem perangkat lunak. Bab ini tidak hanya mengajarkan cara *menggunakan* struktur data, tetapi cara *membangunnya dari nol* — memahami setiap keputusan desain dan implikasinya terhadap performa.

---

#### 📄 [Modul 02.1 — Array, String & Buffer Management](./bab-02/modul-02-1-array-string-buffer.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi + Problem Solving |

**Topik Utama:**
```
2.1.1  Array Statis & Dinamis
        ├── Memory layout: row-major vs column-major
        ├── Dynamic array (ArrayList) — growth strategy
        ├── Amortized analysis push_back O(1)
        └── Multi-dimensional array & matrix representation

2.1.2  Teknik Manipulasi Array
        ├── Two-pointer technique
        ├── Sliding window (fixed & variable size)
        ├── Prefix sum & difference array
        └── Kadane's algorithm (Maximum Subarray)

2.1.3  String Processing
        ├── String sebagai array karakter — immutability
        ├── StringBuilder pattern untuk efisiensi
        ├── String hashing untuk perbandingan O(1)
        └── Unicode & encoding considerations

2.1.4  Circular Buffer & Ring Buffer
        ├── Implementasi circular buffer untuk streaming data
        ├── Aplikasi: audio buffer, network packet buffer
        └── Lock-free circular buffer (konsep dasar)
```

**Problem Set:** 15 soal LeetCode-style (Easy: 8, Medium: 6, Hard: 1)

---

#### 📄 [Modul 02.2 — Linked List (Singly, Doubly, Circular)](./bab-02/modul-02-2-linked-list.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi dari nol + Debugging Lab |

**Topik Utama:**
```
2.2.1  Singly Linked List
        ├── Node structure, pointer manipulation
        ├── Operasi: insert, delete, search, reverse
        ├── Runner technique (fast & slow pointer)
        └── Deteksi & penghapusan cycle (Floyd's Algorithm)

2.2.2  Doubly Linked List
        ├── Implementasi dengan sentinel node
        ├── O(1) insert & delete dengan pointer langsung
        └── Aplikasi: LRU Cache implementation

2.2.3  Circular Linked List
        ├── Implementasi dan traversal
        └── Josephus Problem — aplikasi klasik

2.2.4  Advanced Linked List Problems
        ├── Merge dua sorted linked list
        ├── Reorder list (L0→Ln→L1→Ln-1→...)
        ├── Copy list with random pointer
        └── Skip List — probabilistic data structure
```

**Lab:** Implementasi LRU Cache menggunakan Doubly Linked List + Hash Map (O(1) get & put)

---

#### 📄 [Modul 02.3 — Stack, Queue & Deque](./bab-02/modul-02-3-stack-queue-deque.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi + Aplikasi Sistem Nyata |

**Topik Utama:**
```
2.3.1  Stack
        ├── Implementasi dengan array & linked list
        ├── Monotonic stack — teknik powerful
        ├── Aplikasi: expression evaluation, undo/redo
        └── Call stack simulation & tail call optimization

2.3.2  Queue & Circular Queue
        ├── FIFO semantics, implementasi array circular
        ├── Priority Queue (preview — detail di BAB 03)
        └── Aplikasi: BFS, task scheduling, rate limiting

2.3.3  Deque (Double-Ended Queue)
        ├── Implementasi dengan doubly linked list
        ├── Sliding window maximum menggunakan monotonic deque
        └── Aplikasi: palindrome check, browser history

2.3.4  Aplikasi Industri
        ├── Message queue pattern (Kafka-like sederhana)
        ├── Thread-safe queue (konsep producer-consumer)
        └── Implementasi: Simple Task Queue dengan priority
```

**Deliverable Bab 02:**
> 📝 **Mini Project:** Implementasi **Text Editor Buffer** menggunakan kombinasi Gap Buffer (array) + Undo Stack + Clipboard Queue, dengan analisis kompleksitas setiap operasi.

---

### 📦 BAB 03 — Pohon & Struktur Hierarkis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 03: Pohon & Struktur Hierarkis                                         │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◈ Intermediate                       │
│  Prasyarat: BAB 01-02, rekursi mahir                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Struktur pohon muncul di mana-mana: filesystem, database index (B-Tree), compiler AST, HTML DOM, sistem file konfigurasi. Bab ini membangun intuisi mendalam tentang hierarki data dan cara mengeksploitasinya untuk pencarian dan manipulasi efisien.

---

#### 📄 [Modul 03.1 — Binary Tree & Binary Search Tree (BST)](./bab-03/modul-03-1-binary-tree-bst.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Visualisasi |

**Topik Utama:**
```
3.1.1  Binary Tree Fundamentals
        ├── Terminologi: root, leaf, height, depth, diameter
        ├── Jenis: full, complete, perfect, balanced, degenerate
        ├── Representasi: linked node vs array (heap-style)
        └── Traversal: Inorder, Preorder, Postorder, Level-order

3.1.2  Binary Search Tree (BST)
        ├── BST property dan invariant
        ├── Search, Insert, Delete — implementasi rekursif & iteratif
        ├── Successor & predecessor
        └── Kompleksitas: O(h) operasi, h = O(log n) balanced, O(n) worst

3.1.3  BST Problems & Patterns
        ├── Validasi BST
        ├── Lowest Common Ancestor (LCA)
        ├── Kth smallest/largest element
        ├── BST to sorted doubly linked list
        └── Serialize & deserialize binary tree

3.1.4  Segment Tree (Preview)
        └── Konsep dasar range query — detail di modul lanjutan
```

---

#### 📄 [Modul 03.2 — Balanced Trees (AVL & Red-Black Tree)](./bab-03/modul-03-2-balanced-trees.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori Mendalam + Implementasi Penuh |

**Topik Utama:**
```
3.2.1  Motivasi Self-Balancing Trees
        ├── Masalah degenerate BST (O(n) operasi)
        └── Konsep balance factor dan rotasi

3.2.2  AVL Tree
        ├── Balance factor: |height(left) - height(right)| ≤ 1
        ├── Rotasi: LL, RR, LR, RL
        ├── Insert dengan rebalancing
        ├── Delete dengan rebalancing
        └── Kompleksitas: O(log n) guaranteed

3.2.3  Red-Black Tree
        ├── 5 properti Red-Black Tree
        ├── Insertion: 6 kasus recoloring & rotation
        ├── Deletion: kasus kompleks dengan double-black
        ├── Perbandingan AVL vs RB Tree (kapan pakai mana)
        └── Implementasi di standard library (Java TreeMap, C++ std::map)

3.2.4  B-Tree & B+ Tree
        ├── Motivasi: disk I/O optimization
        ├── B-Tree properties dan operasi
        ├── B+ Tree — semua data di leaf, linked list
        └── Aplikasi: Database index (MySQL InnoDB, PostgreSQL)
```

**Lab:** Implementasi AVL Tree lengkap dengan visualisasi rotasi

---

#### 📄 [Modul 03.3 — Heap, Priority Queue & Trie](./bab-03/modul-03-3-heap-priority-trie.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi + Aplikasi Sistem |

**Topik Utama:**
```
3.3.1  Binary Heap
        ├── Min-heap & Max-heap property
        ├── Array representation: parent = (i-1)/2, children = 2i+1, 2i+2
        ├── Heapify-up (sift-up) & Heapify-down (sift-down)
        ├── Build heap: O(n) — bukti matematis
        └── Heap Sort: O(n log n) in-place

3.3.2  Priority Queue Lanjutan
        ├── d-ary heap untuk cache performance
        ├── Fibonacci Heap — O(1) amortized decrease-key
        ├── Aplikasi: Dijkstra, Prim's MST, A* search
        └── Implementasi: Task scheduler dengan priority

3.3.3  Trie (Prefix Tree)
        ├── Struktur node Trie
        ├── Insert, Search, StartsWith — O(m) per operasi
        ├── Delete dengan backtracking
        ├── Compressed Trie (Patricia Tree / Radix Tree)
        └── Aplikasi: Autocomplete, spell checker, IP routing

3.3.4  Segment Tree & Fenwick Tree (BIT)
        ├── Segment Tree: range query & point update O(log n)
        ├── Lazy propagation untuk range update
        ├── Fenwick Tree (BIT): simpler, cache-friendly
        └── Aplikasi: Range sum, range min/max query
```

**Deliverable Bab 03:**
> 📝 **Mini Project:** Implementasi **Autocomplete Engine** menggunakan Trie dengan fitur: prefix search, frequency-based ranking (menggunakan Min-Heap), dan fuzzy matching sederhana.

---

### 📦 BAB 04 — Hashing & Struktur Data Probabilistik

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 04: Hashing & Struktur Data Probabilistik                              │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◈ Intermediate                       │
│  Prasyarat: BAB 01-03, probabilitas dasar                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Hashing adalah senjata rahasia engineer modern. Dari database join hingga blockchain, dari cache invalidation hingga distributed systems — pemahaman mendalam tentang hashing membuka solusi O(1) untuk masalah yang tampak membutuhkan O(n).

---

#### 📄 [Modul 04.1 — Hash Table: Desain & Collision Resolution](./bab-04/modul-04-1-hash-table-design.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi dari Nol |

**Topik Utama:**
```
4.1.1  Hash Function Design
        ├── Properti hash function yang baik: uniform, deterministic, fast
        ├── Division method, multiplication method
        ├── Polynomial rolling hash untuk string
        ├── Universal hashing & family of hash functions
        └── Cryptographic vs non-cryptographic hash (MD5, SHA, MurmurHash)

4.1.2  Collision Resolution
        ├── Separate Chaining: linked list, BST, atau array
        ├── Open Addressing: Linear, Quadratic, Double Hashing
        ├── Robin Hood Hashing — variance reduction
        ├── Cuckoo Hashing — O(1) worst-case lookup
        └── Load factor & rehashing strategy

4.1.3  Hash Table Analysis
        ├── Expected O(1) dengan analisis probabilistik
        ├── Worst case O(n) dan cara mitigasinya
        ├── Cache performance: chaining vs open addressing
        └── Implementasi HashMap dari nol (Python)

4.1.4  Aplikasi Hash Table
        ├── Two Sum, Group Anagrams, Subarray Sum
        ├── Rabin-Karp string matching (preview)
        └── Implementasi: Simple in-memory cache dengan TTL
```

---

#### 📄 [Modul 04.2 — Bloom Filter, Count-Min Sketch & HyperLogLog](./bab-04/modul-04-2-probabilistic-structures.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Studi Kasus Industri |

**Topik Utama:**
```
4.2.1  Bloom Filter
        ├── Konsep: space-efficient probabilistic membership test
        ├── False positive rate: (1 - e^(-kn/m))^k
        ├── Optimal k (jumlah hash function): k = (m/n) ln 2
        ├── Implementasi dengan bit array
        ├── Counting Bloom Filter untuk deletion
        └── Aplikasi: Google Bigtable, Cassandra, Redis

4.2.2  Count-Min Sketch
        ├── Frequency estimation dengan bounded error
        ├── Estimasi: f̂(x) = min_i{C[i][h_i(x)]}
        ├── Error bound: ε dengan probabilitas 1-δ
        └── Aplikasi: Heavy hitters, network traffic analysis

4.2.3  HyperLogLog
        ├── Cardinality estimation — distinct count
        ├── Algoritma Flajolet-Martin
        ├── HyperLogLog: O(log log n) space untuk ±2% error
        └── Aplikasi: Redis PFCOUNT, Google Analytics

4.2.4  MinHash & Locality Sensitive Hashing (LSH)
        ├── Jaccard similarity estimation
        ├── LSH untuk approximate nearest neighbor
        └── Aplikasi: Duplicate detection, recommendation system
```

---

#### 📄 [Modul 04.3 — Consistent Hashing & Distributed Hash Table](./bab-04/modul-04-3-consistent-hashing-dht.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori Sistem Terdistribusi + Lab |

**Topik Utama:**
```
4.3.1  Consistent Hashing
        ├── Masalah: modular hashing dalam distributed system
        ├── Hash ring (virtual ring) concept
        ├── Virtual nodes untuk load balancing
        ├── Penambahan/penghapusan node: O(K/N) remapping
        └── Implementasi consistent hashing dari nol

4.3.2  Distributed Hash Table (DHT)
        ├── Chord protocol — O(log n) lookup
        ├── Kademlia — XOR metric, used in BitTorrent
        └── Aplikasi: P2P networks, distributed storage

4.3.3  Rendezvous Hashing (Highest Random Weight)
        ├── Alternatif consistent hashing
        └── Perbandingan: consistent vs rendezvous hashing

4.3.4  Aplikasi Enterprise
        ├── Load balancer dengan consistent hashing
        ├── Distributed cache (Memcached, Redis Cluster)
        └── Lab: Simulasi distributed cache dengan consistent hashing
```

**Deliverable Bab 04:**
> 📝 **Mini Project:** Implementasi **Distributed Rate Limiter** menggunakan Bloom Filter (untuk IP blacklist), Count-Min Sketch (untuk request counting), dan Consistent Hashing (untuk distribusi ke multiple nodes).

---

### 📦 BAB 05 — Algoritma Pengurutan & Pencarian

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 05: Algoritma Pengurutan & Pencarian                                   │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◈◉ Intermediate-Advanced             │
│  Prasyarat: BAB 01-04                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Sorting dan searching adalah operasi paling fundamental dalam komputasi. Bab ini tidak hanya mengajarkan algoritma klasik, tetapi mengungkap *mengapa* setiap algoritma dirancang demikian, kapan masing-masing optimal, dan bagaimana memilih yang tepat untuk konteks spesifik.

---

#### 📄 [Modul 05.1 — Sorting Klasik: Merge, Quick & Heap Sort](./bab-05/modul-05-1-sorting-klasik.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi + Analisis Mendalam + Benchmark |

**Topik Utama:**
```
5.1.1  Merge Sort
        ├── Divide & Conquer paradigm
        ├── Implementasi top-down & bottom-up (iteratif)
        ├── Stable sort — mengapa penting
        ├── External merge sort untuk data > RAM
        └── Kompleksitas: O(n log n) all cases, O(n) space

5.1.2  Quick Sort
        ├── Partition scheme: Lomuto vs Hoare
        ├── Pivot selection: first, last, random, median-of-three
        ├── Worst case O(n²) dan cara menghindarinya
        ├── Introsort: Quick + Heap + Insertion (std::sort C++)
        └── 3-way partition (Dutch National Flag) untuk duplicates

5.1.3  Heap Sort
        ├── Build max-heap O(n), extract O(n log n)
        ├── In-place, O(1) space, O(n log n) guaranteed
        ├── Mengapa jarang dipakai meski optimal? (cache miss)
        └── Smoothsort — adaptive variant

5.1.4  Perbandingan & Pemilihan Algoritma
        ├── Benchmark empiris: cache behavior, branch prediction
        ├── Timsort (Python's sort): adaptive merge + insertion
        └── Decision tree: kapan pakai algoritma mana
```

---

#### 📄 [Modul 05.2 — Linear Sorting & External Sort](./bab-05/modul-05-2-linear-external-sort.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Studi Kasus Big Data |

**Topik Utama:**
```
5.2.1  Lower Bound Sorting
        ├── Bukti: comparison-based sort ≥ Ω(n log n)
        └── Decision tree argument

5.2.2  Counting Sort
        ├── O(n + k) untuk integer range [0, k]
        ├── Stable counting sort
        └── Limitasi: hanya untuk integer/bounded range

5.2.3  Radix Sort
        ├── LSD (Least Significant Digit) Radix Sort
        ├── MSD (Most Significant Digit) Radix Sort
        ├── O(d × (n + k)) kompleksitas
        └── Aplikasi: sorting IP addresses, phone numbers

5.2.4  Bucket Sort
        ├── Uniform distribution assumption
        ├── O(n) average case
        └── Aplikasi: sorting floating point numbers

5.2.5  External Sort (Big Data)
        ├── Problem: data tidak muat di RAM
        ├── External merge sort dengan k-way merge
        ├── Replacement selection untuk initial runs
        └── Aplikasi: Database ORDER BY, MapReduce sort phase
```

---

#### 📄 [Modul 05.3 — Binary Search & Variasi Lanjutan](./bab-05/modul-05-3-binary-search-advanced.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Pola + Problem Solving Intensif |

**Topik Utama:**
```
5.3.1  Binary Search Klasik
        ├── Implementasi iteratif & rekursif
        ├── Off-by-one errors — cara menghindari
        ├── Template universal binary search
        └── Kompleksitas: O(log n)

5.3.2  Binary Search Variants
        ├── Lower bound & upper bound (first/last occurrence)
        ├── Search in rotated sorted array
        ├── Search in 2D matrix
        ├── Find peak element
        └── Kth smallest in sorted matrix

5.3.3  Binary Search on Answer
        ├── Paradigma: "minimize maximum" / "maximize minimum"
        ├── Contoh: Koko Eating Bananas, Capacity to Ship
        ├── Aggressive cows, Book allocation
        └── Pola identifikasi masalah binary search on answer

5.3.4  Ternary Search & Interpolation Search
        ├── Ternary search untuk unimodal function
        ├── Interpolation search O(log log n) average
        └── Exponential search untuk unbounded array
```

**Deliverable Bab 05:**
> 📝 **Mini Project:** Implementasi **Multi-Strategy Sorting Library** yang secara otomatis memilih algoritma optimal berdasarkan karakteristik input (ukuran, tipe data, distribusi, memory constraint), dengan benchmark report otomatis.

---

### 📦 BAB 06 — Graf & Algoritma Traversal

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 06: Graf & Algoritma Traversal                                         │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◈◉ Intermediate-Advanced             │
│  Prasyarat: BAB 01-05, rekursi mahir                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Graf adalah model paling ekspresif dalam ilmu komputer. Jaringan sosial, peta navigasi, dependency sistem, sirkuit elektronik, protein interaction — semuanya adalah graf. Bab ini membangun kemampuan memodelkan dan menyelesaikan masalah dunia nyata sebagai masalah graf.

---

#### 📄 [Modul 06.1 — Representasi Graf & BFS/DFS](./bab-06/modul-06-1-representasi-bfs-dfs.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Problem Solving |

**Topik Utama:**
```
6.1.1  Representasi Graf
        ├── Adjacency Matrix: O(V²) space, O(1) edge check
        ├── Adjacency List: O(V+E) space, O(degree) edge check
        ├── Edge List: O(E) space, untuk sparse graph
        ├── Implicit Graph: grid, state space
        └── Pemilihan representasi berdasarkan use case

6.1.2  Breadth-First Search (BFS)
        ├── Implementasi dengan queue
        ├── Level-order traversal
        ├── Shortest path dalam unweighted graph
        ├── Bipartite graph detection
        └── Multi-source BFS

6.1.3  Depth-First Search (DFS)
        ├── Implementasi rekursif & iteratif (stack)
        ├── DFS timestamps: discovery & finish time
        ├── Cycle detection (directed & undirected)
        ├── Connected components
        └── Flood fill & island counting

6.1.4  Aplikasi BFS/DFS
        ├── Word ladder (BFS)
        ├── Number of islands (DFS/BFS)
        ├── Course schedule (cycle detection)
        └── Clone graph
```

---

#### 📄 [Modul 06.2 — Shortest Path Algorithms](./bab-06/modul-06-2-shortest-path.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Studi Kasus Navigasi |

**Topik Utama:**
```
6.2.1  Dijkstra's Algorithm
        ├── Greedy approach dengan priority queue
        ├── Implementasi: O((V+E) log V) dengan binary heap
        ├── Implementasi: O(V²) dengan array (dense graph)
        ├── Limitasi: tidak bisa negative weight
        └── Bidirectional Dijkstra untuk percepatan

6.2.2  Bellman-Ford Algorithm
        ├── Dynamic programming approach
        ├── O(VE) — lebih lambat tapi handle negative weight
        ├── Negative cycle detection
        └── SPFA (Shortest Path Faster Algorithm)

6.2.3  Floyd-Warshall Algorithm
        ├── All-pairs shortest path O(V³)
        ├── DP formulation: dp[k][i][j]
        ├── Negative cycle detection
        └── Transitive closure

6.2.4  A* Search Algorithm
        ├── Heuristic-guided search
        ├── Admissible & consistent heuristic
        ├── Manhattan distance, Euclidean distance
        └── Aplikasi: GPS navigation, game pathfinding
```

---

#### 📄 [Modul 06.3 — MST, Topological Sort & SCC](./bab-06/modul-06-3-mst-topo-scc.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi + Aplikasi Enterprise |

**Topik Utama:**
```
6.3.1  Minimum Spanning Tree (MST)
        ├── Kruskal's Algorithm: sort edges + Union-Find O(E log E)
        ├── Prim's Algorithm: greedy + priority queue O(E log V)
        ├── Borůvka's Algorithm: parallel-friendly
        └── Aplikasi: network design, cluster analysis

6.3.2  Union-Find (Disjoint Set Union)
        ├── Union by rank & path compression
        ├── Amortized O(α(n)) ≈ O(1) per operasi
        └── Aplikasi: MST, dynamic connectivity, percolation

6.3.3  Topological Sort
        ├── Kahn's Algorithm (BFS-based)
        ├── DFS-based topological sort
        ├── Unique topological order detection
        └── Aplikasi: build systems, dependency resolution, course scheduling

6.3.4  Strongly Connected Components (SCC)
        ├── Kosaraju's Algorithm: 2 DFS passes
        ├── Tarjan's Algorithm: 1 DFS dengan stack
        ├── Condensation graph (DAG of SCCs)
        └── Aplikasi: compiler optimization, social network analysis
```

**Deliverable Bab 06:**
> 📝 **Mini Project:** Implementasi **Campus Navigation System** — sistem navigasi kampus dengan fitur: shortest path (Dijkstra), alternative routes (k-shortest paths), accessibility routing (constraint-based), dan visualisasi graf interaktif.

---

### 📦 BAB 07 — Divide & Conquer + Greedy Algorithms

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 07: Divide & Conquer + Greedy Algorithms                               │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◉ Advanced                           │
│  Prasyarat: BAB 01-06                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Dua paradigma yang sering disalahpahami. Divide & Conquer memecah masalah menjadi submasalah *independen*. Greedy membuat keputusan lokal optimal dengan harapan menghasilkan solusi global optimal — dan bab ini mengajarkan cara *membuktikan* kapan greedy benar-benar bekerja.

---

#### 📄 [Modul 07.1 — Divide & Conquer: Paradigma & Aplikasi](./bab-07/modul-07-1-divide-conquer.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Analisis |

**Topik Utama:**
```
7.1.1  Paradigma Divide & Conquer
        ├── 3 langkah: Divide, Conquer, Combine
        ├── Identifikasi subproblem yang independen
        └── Analisis dengan Master Theorem

7.1.2  Algoritma D&C Klasik
        ├── Merge Sort & Quick Sort (review mendalam)
        ├── Binary Search sebagai D&C
        ├── Maximum Subarray (Kadane vs D&C)
        └── Closest Pair of Points: O(n log n)

7.1.3  Algoritma D&C Lanjutan
        ├── Strassen Matrix Multiplication: O(n^2.807)
        ├── Karatsuba Algorithm: fast integer multiplication
        ├── Fast Fourier Transform (FFT): O(n log n) polynomial multiply
        └── Aplikasi FFT: signal processing, polynomial multiplication

7.1.4  Parallel D&C
        ├── Parallelism dalam D&C — work & span analysis
        └── Aplikasi: parallel merge sort, MapReduce
```

---

#### 📄 [Modul 07.2 — Greedy Algorithm: Correctness Proof](./bab-07/modul-07-2-greedy-correctness.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori Formal + Problem Solving |

**Topik Utama:**
```
7.2.1  Greedy Paradigm
        ├── Greedy choice property
        ├── Optimal substructure
        └── Perbedaan greedy vs DP

7.2.2  Teknik Pembuktian Greedy
        ├── Exchange argument (swap argument)
        ├── Greedy stays ahead
        └── Matroid theory (konsep dasar)

7.2.3  Greedy Problems Klasik
        ├── Activity Selection / Interval Scheduling
        ├── Fractional Knapsack
        ├── Job Sequencing with Deadlines
        └── Gas Station Problem

7.2.4  Greedy yang Salah & Cara Mendeteksinya
        ├── 0/1 Knapsack — mengapa greedy gagal
        ├── Coin change — kapan greedy benar, kapan salah
        └── Counterexample construction technique
```

---

#### 📄 [Modul 07.3 — Interval Scheduling, Huffman & Kruskal](./bab-07/modul-07-3-aplikasi-greedy.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi + Aplikasi Industri |

**Topik Utama:**
```
7.3.1  Interval Scheduling & Partitioning
        ├── Interval Scheduling Maximization
        ├── Interval Partitioning (minimum rooms)
        ├── Weighted Interval Scheduling (DP approach)
        └── Aplikasi: calendar scheduling, resource allocation

7.3.2  Huffman Coding
        ├── Prefix-free codes & binary trie
        ├── Huffman algorithm dengan priority queue
        ├── Proof of optimality
        ├── Adaptive Huffman coding
        └── Aplikasi: ZIP, JPEG, MP3 compression

7.3.3  Kruskal & Prim Revisited (Greedy Proof)
        ├── Proof MST algorithms menggunakan cut property
        └── Matroid intersection untuk generalisasi

7.3.4  Advanced Greedy Applications
        ├── Dijkstra sebagai greedy (proof)
        ├── Scheduling untuk minimize lateness
        └── Set cover approximation (greedy ≈ ln n optimal)
```

**Deliverable Bab 07:**
> 📝 **Mini Project:** Implementasi **File Compression Tool** menggunakan Huffman Coding dengan fitur: encoding, decoding, compression ratio analysis, dan perbandingan dengan algoritma lain (LZ77 preview).

---

### 📦 BAB 08 — Dynamic Programming

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 08: Dynamic Programming                                                │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ◉ Advanced                           │
│  Prasyarat: BAB 01-07, rekursi mahir, matematika kombinatorik               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Dynamic Programming adalah puncak dari pemikiran algoritmik. Bab ini mengajarkan cara mengidentifikasi struktur optimal dalam masalah, mendefinisikan state DP yang tepat, dan mengoptimalkan solusi dari O(2ⁿ) menjadi O(n²) atau bahkan O(n log n).

---

#### 📄 [Modul 08.1 — DP Fundamentals: Memoization & Tabulation](./bab-08/modul-08-1-dp-fundamentals.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Pola Identifikasi + Latihan |

**Topik Utama:**
```
8.1.1  Dua Properti DP
        ├── Optimal substructure: solusi optimal mengandung subsolusi optimal
        ├── Overlapping subproblems: submasalah yang sama dihitung berulang
        └── Perbedaan dengan D&C (subproblem tidak overlap)

8.1.2  Top-Down DP (Memoization)
        ├── Rekursi + cache (dictionary/array)
        ├── Fibonacci, Climbing Stairs, House Robber
        ├── Implementasi decorator @lru_cache Python
        └── Analisis kompleksitas: state × transition

8.1.3  Bottom-Up DP (Tabulation)
        ├── Iteratif, isi tabel dari base case
        ├── Topological order pengisian tabel
        ├── Space optimization: rolling array
        └── Perbandingan top-down vs bottom-up

8.1.4  Framework Identifikasi DP
        ├── Pola: "minimum/maximum", "count ways", "is possible"
        ├── State definition — kunci utama DP
        ├── Transition function derivation
        └── Base case identification
```

---

#### 📄 [Modul 08.2 — DP Klasik: Knapsack, LCS, LIS, Edit Distance](./bab-08/modul-08-2-dp-klasik.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Implementasi Mendalam + Variasi |

**Topik Utama:**
```
8.2.1  Knapsack Problems
        ├── 0/1 Knapsack: O(nW) DP
        ├── Unbounded Knapsack: item tak terbatas
        ├── Bounded Knapsack: item dengan jumlah terbatas
        ├── Fractional Knapsack: greedy (review)
        └── Variasi: partition equal subset sum, target sum

8.2.2  Sequence DP
        ├── Longest Common Subsequence (LCS): O(mn)
        ├── Longest Increasing Subsequence (LIS): O(n²) & O(n log n)
        ├── Longest Common Substring
        └── Shortest Common Supersequence

8.2.3  Edit Distance & String DP
        ├── Levenshtein Distance: insert, delete, replace
        ├── Alignment problem (bioinformatics)
        ├── Wildcard matching & regex matching
        └── Palindrome DP: longest palindromic subsequence

8.2.4  Matrix & Grid DP
        ├── Unique Paths, Minimum Path Sum
        ├── Maximal Square, Maximal Rectangle
        ├── Dungeon Game (reverse DP)
        └── Matrix Chain Multiplication: O(n³)
```

---

#### 📄 [Modul 08.3 — DP Lanjutan: Bitmask, Trees & Graphs](./bab-08/modul-08-3-dp-advanced.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teknik Advanced + Problem Solving Kompetitif |

**Topik Utama:**
```
8.3.1  Bitmask DP
        ├── Representasi subset dengan bitmask
        ├── Traveling Salesman Problem (TSP): O(2ⁿ × n²)
        ├── Minimum Cost to Visit All Nodes
        └── Assignment Problem dengan bitmask

8.3.2  DP on Trees
        ├── Tree DP — state pada subtree
        ├── Diameter of tree dengan DP
        ├── Maximum Independent Set on Tree
        ├── Tree knapsack
        └── Rerooting technique

8.3.3  DP on Graphs
        ├── DP pada DAG (topological order)
        ├── Shortest path sebagai DP (Bellman-Ford)
        ├── Counting paths dalam DAG
        └── DP dengan state kompresi

8.3.4  Optimasi DP
        ├── Divide & Conquer optimization: O(n² → n log n)
        ├── Convex Hull Trick (CHT): O(n² → n)
        ├── Knuth's optimization: O(n³ → n²)
        └── Monotone queue optimization
```

**Deliverable Bab 08:**
> 📝 **Mini Project:** Implementasi **Optimal Route Planner** — sistem perencanaan rute dengan constraint (budget, waktu, kapasitas) menggunakan kombinasi DP (multi-dimensional knapsack) + Graf (shortest path), dengan interface CLI interaktif.

---

### 📦 BAB 09 — Algoritma String & Komputasi Geometri

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 09: Algoritma String & Komputasi Geometri                              │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ★ Expert                             │
│  Prasyarat: BAB 01-08                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Algoritma string adalah jantung dari search engine, bioinformatics, dan natural language processing. Komputasi geometri mendukung GIS, computer graphics, dan robotics. Bab ini membuka domain spesialisasi yang sangat dicari industri.

---

#### 📄 [Modul 09.1 — String Matching: KMP, Rabin-Karp & Aho-Corasick](./bab-09/modul-09-1-string-matching.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori Mendalam + Implementasi + Aplikasi |

**Topik Utama:**
```
9.1.1  Naive String Matching: O(nm)
        └── Baseline untuk perbandingan

9.1.2  KMP (Knuth-Morris-Pratt): O(n+m)
        ├── Failure function (partial match table)
        ├── Konstruksi failure function O(m)
        ├── Matching dengan failure function O(n)
        └── Aplikasi: find all occurrences

9.1.3  Rabin-Karp: O(n+m) average
        ├── Rolling hash untuk sliding window
        ├── Multiple pattern matching
        └── Aplikasi: plagiarism detection, 2D pattern matching

9.1.4  Aho-Corasick: O(n + m_total + k)
        ├── Trie + failure links (BFS construction)
        ├── Matching multiple patterns simultaneously
        └── Aplikasi: antivirus signature matching, keyword filtering

9.1.5  Boyer-Moore & Sunday Algorithm
        ├── Bad character & good suffix heuristic
        └── Sublinear average case performance
```

---

#### 📄 [Modul 09.2 — Suffix Array, Suffix Tree & Z-Algorithm](./bab-09/modul-09-2-suffix-structures.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Bioinformatics Lab |

**Topik Utama:**
```
9.2.1  Z-Algorithm: O(n)
        ├── Z-array: Z[i] = length of longest substring starting at i
        │           yang merupakan prefix dari string
        ├── Konstruksi O(n) dengan Z-box
        └── Aplikasi: pattern matching, string periodicity

9.2.2  Suffix Array
        ├── Definisi: sorted array of all suffixes
        ├── Naive construction: O(n² log n)
        ├── O(n log n) construction (prefix doubling)
        ├── SA-IS: O(n) linear construction
        └── LCP Array (Longest Common Prefix)

9.2.3  Suffix Tree
        ├── Ukkonen's Algorithm: O(n) online construction
        ├── Suffix tree vs suffix array trade-off
        └── Aplikasi: longest repeated substring, longest common substring

9.2.4  Aplikasi Suffix Structures
        ├── Longest Repeated Substring
        ├── Longest Common Substring (multiple strings)
        ├── String compression (BWT — Burrows-Wheeler Transform)
        └── Bioinformatics: DNA sequence alignment
```

---

#### 📄 [Modul 09.3 — Computational Geometry: Convex Hull & Line Sweep](./bab-09/modul-09-3-computational-geometry.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Visualisasi |

**Topik Utama:**
```
9.3.1  Geometric Primitives
        ├── Cross product & orientation test
        ├── Point in polygon (ray casting)
        ├── Line segment intersection
        └── Area of polygon (Shoelace formula)

9.3.2  Convex Hull
        ├── Graham Scan: O(n log n)
        ├── Jarvis March (Gift Wrapping): O(nh)
        ├── Chan's Algorithm: O(n log h) optimal
        └── Aplikasi: collision detection, GIS, robot motion planning

9.3.3  Line Sweep Algorithm
        ├── Event-driven paradigm
        ├── Segment intersection (Bentley-Ottmann): O((n+k) log n)
        ├── Closest pair of points: O(n log n)
        └── Area of union of rectangles

9.3.4  Voronoi Diagram & Delaunay Triangulation
        ├── Fortune's Algorithm: O(n log n)
        ├── Duality: Voronoi ↔ Delaunay
        └── Aplikasi: nearest neighbor, mesh generation, GIS
```

**Deliverable Bab 09:**
> 📝 **Mini Project:** Implementasi **Plagiarism Detection Engine** menggunakan Rabin-Karp (fingerprinting), Aho-Corasick (multi-pattern matching), Suffix Array (longest common substring), dan MinHash (similarity estimation) — diuji pada corpus dokumen nyata.

---

### 📦 BAB 10 — Algoritma Advanced & Sistem Terdistribusi

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BAB 10: Algoritma Advanced & Sistem Terdistribusi                          │
│  Durasi: 2 Minggu (24 Jam) │ Tingkat: ★ Expert                             │
│  Prasyarat: BAB 01-09 selesai                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Deskripsi Bab:**
Bab penutup yang menjembatani teori algoritma dengan realitas sistem produksi skala besar. Dari network flow yang mendasari matching platform, hingga algoritma randomized yang membuat sistem terdistribusi toleran terhadap kegagalan.

---

#### 📄 [Modul 10.1 — Network Flow, Matching & Linear Programming](./bab-10/modul-10-1-network-flow-matching.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori + Implementasi + Aplikasi Enterprise |

**Topik Utama:**
```
10.1.1  Maximum Flow
         ├── Flow network: source, sink, capacity
         ├── Ford-Fulkerson: O(E × max_flow)
         ├── Edmonds-Karp (BFS augmenting path): O(VE²)
         ├── Dinic's Algorithm: O(V²E)
         └── Push-relabel: O(V²√E)

10.1.2  Min-Cut Max-Flow Theorem
         ├── Dualitas max-flow & min-cut
         └── Aplikasi: network reliability, image segmentation

10.1.3  Bipartite Matching
         ├── Maximum bipartite matching via max-flow
         ├── Hopcroft-Karp: O(E√V)
         ├── Hungarian Algorithm: O(n³) assignment problem
         └── Aplikasi: job assignment, ride-sharing matching

10.1.4  Linear Programming (Pengantar)
         ├── LP formulation: objective + constraints
         ├── Simplex method (konsep)
         ├── LP duality
         └── Aplikasi: resource allocation, network optimization
```

---

#### 📄 [Modul 10.2 — Randomized Algorithms & Approximation](./bab-10/modul-10-2-randomized-approximation.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Teori Probabilistik + Implementasi |

**Topik Utama:**
```
10.2.1  Randomized Algorithms
         ├── Las Vegas vs Monte Carlo algorithms
         ├── Randomized QuickSort: expected O(n log n)
         ├── Randomized QuickSelect: expected O(n)
         ├── Treap: randomized BST
         └── Skip List: O(log n) expected

10.2.2  Hashing Randomized
         ├── Universal hashing — collision probability 1/m
         ├── Perfect hashing: O(1) worst-case lookup
         └── Cuckoo hashing revisited

10.2.3  Approximation Algorithms
         ├── Approximation ratio & PTAS/FPTAS
         ├── Vertex Cover: 2-approximation
         ├── TSP: Christofides 1.5-approximation
         ├── Set Cover: O(log n)-approximation
         └── Bin Packing: First Fit Decreasing

10.2.4  NP-Completeness (Pengantar)
         ├── P vs NP problem
         ├── NP-Complete problems: SAT, 3-SAT, Clique, Vertex Cover
         ├── Reduction technique
         └── Implikasi praktis: kapan cari approximation
```

---

#### 📄 [Modul 10.3 — DSA dalam Sistem Terdistribusi & Cloud](./bab-10/modul-10-3-dsa-distributed-systems.md)

| Atribut | Detail |
|---------|--------|
| **Durasi** | 8 Jam | **Format** | Studi Kasus Industri + Lab Terdistribusi |

**Topik Utama:**
```
10.3.1  Algoritma Konsensus
         ├── Paxos: consensus in distributed systems
         ├── Raft: understandable consensus
         ├── Byzantine fault tolerance (BFT)
         └── Aplikasi: etcd, ZooKeeper, distributed databases

10.3.2  Struktur Data Terdistribusi
         ├── Distributed hash table (revisit — implementasi)
         ├── CRDTs (Conflict-free Replicated Data Types)
         ├── Vector clocks & Lamport timestamps
         └── Merkle Tree: data integrity verification

10.3.3  Algoritma untuk Big Data
         ├── MapReduce paradigm & algoritma
         ├── Streaming algorithms: Reservoir Sampling
         ├── Sketching algorithms (review + aplikasi)
         └── Approximate query processing

10.3.4  Cache & Memory Hierarchy Algorithms
         ├── Cache replacement: LRU, LFU, ARC, CLOCK
         ├── Cache-oblivious algorithms
         ├── Memory-mapped data structures
         └── NUMA-aware data structures

10.3.5  DSA dalam Machine Learning Systems
         ├── KD-Tree & Ball Tree untuk nearest neighbor
         ├── Approximate Nearest Neighbor (FAISS, HNSW)
         ├── Inverted index untuk information retrieval
         └── Graph algorithms dalam GNN (Graph Neural Network)
```

**Deliverable Bab 10:**
> 📝 **Persiapan Capstone:** Desain arsitektur sistem untuk Capstone Project, identifikasi algoritma yang akan digunakan, dan proof-of-concept untuk komponen kritis.

---

## 4. Spesifikasi Capstone Project Enterprise

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║         CAPSTONE PROJECT ENTERPRISE — GEMINI-DSA-001                        ║
║                                                                              ║
║    "Distributed Search & Recommendation Engine"                              ║
║    (Mesin Pencari & Rekomendasi Terdistribusi)                               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 4.1 Deskripsi Proyek

Peserta akan membangun sistem **Search & Recommendation Engine** skala enterprise yang menggabungkan seluruh konsep DSA yang dipelajari dalam satu sistem terintegrasi. Sistem ini mensimulasikan infrastruktur yang digunakan oleh platform e-commerce atau media besar (seperti Tokopedia, Shopee, atau Netflix) untuk melayani jutaan pengguna.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARSITEKTUR SISTEM CAPSTONE                               │
│                                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────────────────┐   │
│  │  Client  │───▶│  API Gateway │───▶│         Search Engine           │   │
│  │  (CLI/   │    │  (Rate Limit │    │  ┌─────────────────────────┐   │   │
│  │   HTTP)  │    │  + Auth)     │    │  │  Query Parser & Analyzer │   │   │
│  └──────────┘    └──────────────┘    │  └──────────┬──────────────┘   │   │
│                                      │             │                   │   │
│  ┌──────────────────────────────┐    │  ┌──────────▼──────────────┐   │   │
│  │     Recommendation Engine    │    │  │   Inverted Index (Trie  │   │   │
│  │  ┌────────────────────────┐  │    │  │   + Suffix Array)       │   │   │
│  │  │  Collaborative Filter  │  │    │  └──────────┬──────────────┘   │   │
│  │  │  (Graph-based)         │  │    │             │                   │   │
│  │  └────────────────────────┘  │    │  ┌──────────▼──────────────┐   │   │
│  │  ┌────────────────────────┐  │    │  │   Ranking Engine        │   │   │
│  │  │  Content-Based Filter  │  │    │  │   (BM25 + PageRank)     │   │   │
│  │  │  (MinHash + LSH)       │  │    │  └─────────────────────────┘   │   │
│  │  └────────────────────────┘  │    └─────────────────────────────────┘   │
│  └──────────────────────────────┘                                           │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    DISTRIBUTED STORAGE LAYER                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │  │
│  │  │  Node 1     │  │  Node 2     │  │  Node 3     │  │  Node N   │  │  │
│  │  │  (Shard A)  │  │  (Shard B)  │  │  (Shard C)  │  │  (...)    │  │  │
│  │  │  Hash Ring  │  │  Hash Ring  │  │  Hash Ring  │  │           │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Komponen Sistem & Algoritma yang Digunakan

| Komponen | Algoritma/DS yang Digunakan | Bab Referensi |
|----------|----------------------------|---------------|
| **Query Parser** | Trie (autocomplete), Aho-Corasick (multi-keyword) | BAB 03, 09 |
| **Inverted Index** | Hash Map + Suffix Array + Posting List | BAB 04, 09 |
| **Ranking Engine** | BM25 scoring + PageRank (Power Iteration) | BAB 06, 08 |
| **Spell Checker** | Edit Distance (DP) + BK-Tree | BAB 08, 09 |
| **Rate Limiter** | Sliding Window Counter + Bloom Filter | BAB 02, 04 |
| **Cache Layer** | LRU Cache (DLL + HashMap) + LFU Cache | BAB 02, 03 |
| **Collaborative Filter** | Graph BFS/DFS + Matrix Factorization | BAB 06 |
| **Content Filter** | MinHash + LSH + Jaccard Similarity | BAB 04 |
| **Distributed Storage** | Consistent Hashing + Merkle Tree | BAB 04, 10 |
| **Load Balancer** | Consistent Hashing + Health Check | BAB 04, 10 |
| **Analytics** | HyperLogLog (DAU) + Count-Min Sketch (trending) | BAB 04 |
| **Compression** | Huffman Coding + LZ77 | BAB 07 |

### 4.3 Spesifikasi Teknis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SPESIFIKASI TEKNIS CAPSTONE PROJECT                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BAHASA PEMROGRAMAN:                                                        │
│    Primary   : Python 3.11+ (core algorithms & API)                        │
│    Secondary : Go / Java (performance-critical components, opsional)        │
│                                                                             │
│  DATASET:                                                                   │
│    - Wikipedia articles dump (subset 100K dokumen)                          │
│    - Synthetic user interaction logs (1M events)                            │
│    - Product catalog dataset (50K items)                                    │
│                                                                             │
│  PERFORMA TARGET:                                                           │
│    - Search latency: P95 < 100ms untuk 10K concurrent users                │
│    - Indexing throughput: > 1000 dokumen/detik                              │
│    - Recommendation: P95 < 200ms                                            │
│    - Cache hit rate: > 80%                                                  │
│    - Availability: 99.9% (simulasi dengan fault injection)                  │
│                                                                             │
│  SKALA:                                                                     │
│    - Corpus: 100K dokumen, ~500MB total                                     │
│    - Concurrent users: simulasi 10K users                                   │
│    - Distributed nodes: minimum 3 nodes (simulasi dengan Docker)            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Milestone & Timeline

```
MINGGU 17-18: FASE DESAIN & FONDASI
├── [M1] Dokumen Arsitektur Sistem (Architecture Decision Records)
├── [M2] Implementasi Inverted Index + Query Parser
├── [M3] Implementasi Ranking Engine (BM25)
└── [M4] Unit tests untuk semua komponen core

MINGGU 19: FASE INTEGRASI
├── [M5] Implementasi Recommendation Engine
├── [M6] Implementasi Distributed Storage Layer
├── [M7] Implementasi Cache & Rate Limiter
└── [M8] Integration tests & performance profiling

MINGGU 20: FASE OPTIMASI & PRESENTASI
├── [M9] Performance optimization berdasarkan profiling
├── [M10] Load testing & benchmark report
├── [M11] Dokumentasi teknis lengkap
└── [M12] Demo & presentasi (30 menit)
```

### 4.5 Struktur Repository

```
capstone-search-engine/
│
├── README.md                          # Dokumentasi utama
├── ARCHITECTURE.md                    # Keputusan arsitektur (ADR)
├── BENCHMARK.md                       # Hasil benchmark & analisis
│
├── src/
│   ├── core/
│   │   ├── data_structures/
│   │   │   ├── trie.py               # Trie implementation
│   │   │   ├── bloom_filter.py       # Bloom Filter
│   │   │   ├── lru_cache.py          # LRU Cache (DLL + HashMap)
│   │   │   ├── consistent_hash.py    # Consistent Hashing
│   │   │   └── hyperloglog.py        # HyperLogLog
│   │   │
│   │   ├── algorithms/
│   │   │   ├── aho_corasick.py       # Multi-pattern matching
│   │   │   ├── suffix_array.py       # Suffix Array + LCP
│   │   │   ├── edit_distance.py      # DP Edit Distance
│   │   │   ├── huffman.py            # Huffman Coding
│   │   │   └── pagerank.py           # PageRank (Power Iteration)
│   │   │
│   │   └── search/
│   │       ├── inverted_index.py     # Inverted Index Engine
│   │       ├── query_parser.py       # Query Parser & Analyzer
│   │       ├── bm25_ranker.py        # BM25 Ranking
│   │       └── spell_checker.py      # Spell Checker (DP + BK-Tree)
│   │
│   ├── recommendation/
│   │   ├── collaborative_filter.py   # Graph-based CF
│   │   ├── content_filter.py         # MinHash + LSH
│   │   └── hybrid_recommender.py     # Hybrid approach
│   │
│   ├── distributed/
│   │   ├── storage_node.py           # Storage Node simulation
│   │   ├── load_balancer.py          # Load Balancer
│   │   └── merkle_tree.py            # Data integrity
│   │
│   ├── api/
│   │   ├── gateway.py                # API Gateway + Rate Limiter
│   │   ├── search_handler.py         # Search endpoint
│   │   └── recommend_handler.py      # Recommendation endpoint
│   │
│   └── analytics/
│       ├── count_min_sketch.py       # Trending topics
│       └── hyperloglog_tracker.py    # DAU tracking
│
├── tests/
│   ├── unit/                         # Unit tests per komponen
│   ├── integration/                  # Integration tests
│   └── stress/                       # Stress & load tests
│
├── benchmarks/
│   ├── benchmark_search.py           # Search performance benchmark
│   ├── benchmark_index.py            # Indexing benchmark
│   └── results/                      # Benchmark results (JSON/CSV)
│
├── data/
│   ├── corpus/                       # Document corpus
│   ├── queries/                      # Test queries
│   └── synthetic/                    # Synthetic user logs
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml            # Multi-node setup
│   └── node-config/                  # Per-node configuration
│
└── docs/
    ├── api-reference.md              # API documentation
    ├── algorithm-analysis.md         # Complexity analysis semua komponen
    └── performance-report.md         # Final performance report
```

### 4.6 Kriteria Penilaian Capstone

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RUBRIK PENILAIAN CAPSTONE PROJECT (Total: 1000 Poin)                      │
├──────────────────────────────────────────┬──────────┬──────────────────────┤
│  KATEGORI                                │  BOBOT   │  DESKRIPSI           │
├──────────────────────────────────────────┼──────────┼──────────────────────┤
│  1. Kebenaran Implementasi               │  250 pts │  Semua algoritma     │
│     (Correctness)                        │          │  berjalan benar,     │
│                                          │          │  lulus semua tests   │
├──────────────────────────────────────────┼──────────┼──────────────────────┤
│  2. Analisis Kompleksitas                │  200 pts │  Dokumentasi Big-O   │
│     (Complexity Analysis)                │          │  akurat untuk setiap │
│                                          │          │  komponen            │
├──────────────────────────────────────────┼──────────┼──────────────────────┤
│  3. Performa Sistem                      │  200 pts │  Memenuhi target     │
│     (Performance)                        │          │  latency & throughput│
│                                          │          │  yang ditetapkan     │
├──────────────────────────────────────────┼──────────┼──────────────────────┤
│  4. Kualitas Kode & Arsitektur           │  150 pts │  Clean code, SOLID,  │
│     (Code Quality)                       │          │  modular, testable   │
├──────────────────────────────────────────┼──────────┼──────────────────────┤
│  5. Dokumentasi Teknis                   │  100 pts │  README, ADR,        │
│     (Documentation)                      │          │  algorithm analysis  │
├──────────────────────────────────────────┼──────────┼──────────────────────┤
│  6. Presentasi & Demo                    │  100 pts │  Kemampuan           │
│     (Presentation)                       │          │  menjelaskan trade-  │
│                                          │          │  off & keputusan     │
├──────────────────────────────────────────┼──────────┼──────────────────────┤
│  BONUS: Inovasi & Fitur Tambahan         │  +100 pts│  Fitur beyond spec,  │
│                                          │          │  optimasi kreatif    │
└──────────────────────────────────────────┴──────────┴──────────────────────┘

GRADE THRESHOLD:
  ★★★★★  Distinction  : 900-1000 pts  (+ Bonus Certificate)
  ★★★★   Excellence   : 800-899 pts
  ★★★    Proficient   : 700-799 pts
  ★★     Developing   : 600-699 pts
  ★      Needs Work   : < 600 pts     (Revisi wajib)
```

---

## 5. Penilaian & Sertifikasi

### 5.1 Komponen Penilaian Keseluruhan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STRUKTUR PENILAIAN KURSUS GEMINI-DSA-001                                  │
├────────────────────────────────────────┬────────────┬───────────────────────┤
│  KOMPONEN                              │  BOBOT     │  KETERANGAN           │
├────────────────────────────────────────┼────────────┼───────────────────────┤
│  Kuis per Modul (30 kuis)              │  15%       │  Otomatis, 30 menit   │
│  Problem Set per Bab (10 set)          │  20%       │  LeetCode-style       │
│  Mini Project per Bab (10 proyek)      │  25%       │  Peer review          │
│  Ujian Tengah Kursus (Bab 1-5)         │  15%       │  3 jam, open notes    │
│  Capstone Project Enterprise           │  25%       │  Lihat Bagian 4       │
├────────────────────────────────────────┼────────────┼───────────────────────┤
│  TOTAL                                 │  100%      │                       │
└────────────────────────────────────────┴────────────┴───────────────────────┘
```

### 5.2 Jalur Sertifikasi

```
GEMINI-DSA-001 CERTIFICATE TRACKS:

  Track A: GEMINI DSA Practitioner
  ├── Syarat: Nilai akhir ≥ 70%
  ├── Semua Problem Set selesai
  └── Capstone Project lulus (≥ 600 pts)

  Track B: GEMINI DSA Professional  
  ├── Syarat: Nilai akhir ≥ 85%
  ├── Semua Mini Project mendapat ≥ 80%
  └── Capstone Project Excellence (≥ 800 pts)

  Track C: GEMINI DSA Expert (Distinction)
  ├── Syarat: Nilai akhir ≥ 95%
  ├── Kontribusi ke open-source DSA library
  └── Capstone Project Distinction (≥ 900 pts)
```

---

## 6. Referensi & Sumber Daya

### 6.1 Buku Teks Utama

| Prioritas | Judul | Penulis | Relevansi |
|-----------|-------|---------|-----------|
| ⭐⭐⭐ | *Introduction to Algorithms (CLRS), 4th Ed.* | Cormen, Leiserson, Rivest, Stein | Referensi utama, semua bab |
| ⭐⭐⭐ | *Algorithm Design* | Kleinberg & Tardos | BAB 07-08, greedy & DP |
| ⭐⭐ | *The Algorithm Design Manual, 3rd Ed.* | Skiena | Praktis, problem-oriented |
| ⭐⭐ | *Competitive Programmer's Handbook* | Laaksonen | BAB 08-10, advanced topics |
| ⭐⭐ | *Designing Data-Intensive Applications* | Kleppmann | BAB 04, 10, distributed |
| ⭐ | *Programming Pearls* | Bentley | Mindset & problem solving |

### 6.2 Platform Latihan Online

| Platform | Fokus | Link |
|----------|-------|------|
| **LeetCode** | Interview problems, semua tingkat | leetcode.com |
| **Codeforces** | Competitive programming | codeforces.com |
| **USACO** | Algoritma lanjutan | usaco.org |
| **HackerRank** | Structured learning path | hackerrank.com |
| **VisuAlgo** | Visualisasi algoritma | visualgo.net |

### 6.3 Tools & Environment Setup

```bash
# Setup Environment (Python)
python -m venv dsa-env
source dsa-env/bin/activate  # Linux/Mac
# dsa-env\Scripts\activate   # Windows

pip install pytest pytest-cov memory-profiler line-profiler
pip install matplotlib numpy networkx  # Visualisasi
pip install sortedcontainers           # Sorted data structures

# Setup untuk Java (opsional)
# Gunakan IntelliJ IDEA + JUnit 5

# Struktur direktori kerja
mkdir -p dsa-workspace/{bab-{01..10},capstone}
```

### 6.4 Komunitas & Dukungan

```
SALURAN DUKUNGAN:
  ├── Forum Diskusi    : forum.gemini-academy.id/dsa
  ├── Discord Server   : discord.gg/gemini-dsa
  ├── Office Hours     : Setiap Rabu & Sabtu, 19:00-21:00 WIB
  ├── Code Review      : Pull Request ke repo kursus
  └── Peer Study Group : Dibentuk per 5 peserta (minggu pertama)

MENTOR SUPPORT:
  ├── Async (Forum)    : Response dalam 24 jam
  ├── Sync (Discord)   : Response dalam 4 jam (jam kerja)
  └── 1-on-1 Session  : 2x per peserta per bulan (booking via portal)
```

---

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  GEMINI-DSA-001 | Data Structures & Algorithms
  Versi Dokumen  : 2.1.0
  Terakhir Diperbarui : 2025-01-01
  Standar        : roadmap.sh/datastructures-and-algorithms
  
  © 2025 GEMINI Academy — Hak Cipta Dilindungi
  Dokumen ini boleh didistribusikan untuk keperluan pendidikan
  dengan mencantumkan atribusi yang sesuai.

  "The best algorithm is the one you understand deeply enough
   to know when NOT to use it." — GEMINI DSA Principle

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```