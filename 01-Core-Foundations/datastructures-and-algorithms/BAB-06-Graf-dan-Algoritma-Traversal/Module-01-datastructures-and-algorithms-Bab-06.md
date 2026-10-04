# MODUL 06-01: GRAF & ALGORITMA TRAVERSAL FUNDAMENTAL

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `DSA-01-06-01`
* **Kategori**: `01-Core-Foundations`
* **Kurikulum**: `Data Structures & Algorithms (DSA)`
* **Tingkat Kesulitan**: `Intermediate`
* **Prasyarat**:
  * Pemahaman mendalam tentang Struktur Data Linear (Array, Linked List, Stack, Queue).
  * Pemahaman Rekursi dan Rekonstruksi Call Stack.
  * Kompleksitas Waktu dan Ruang Asimptotik (Big-O Notation).
* **Alokasi Waktu**: 6–8 Jam Studi Mandiri & Praktik Mandiri
* **Stack Teknis**: Python 3.11+ (Type Annotations, Abstract Base Classes), visualisasi mental berbasis memori dan pointer.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Mengontraskan** representasi graf struktural (*Adjacency Matrix* vs. *Adjacency List*) serta memilih struktur data yang optimal berdasarkan kerapatan (*density*) graf $\frac{|E|}{|V|^2}$.
2. **Mengimplementasikan** algoritma *Breadth-First Search* (BFS) iteratif menggunakan antrean (*FIFO Queue*) untuk menemukan lintasan terpendek (*shortest path*) pada graf tak berbobot (*unweighted graph*).
3. **Mengimplementasikan** algoritma *Depth-First Search* (DFS) baik secara rekursif maupun iteratif menggunakan tumpukan (*LIFO Stack*) untuk penjelajahan mendalam dan penelusuran balik (*backtracking*).
4. **Mendeteksi Siklus (*Cycle Detection*)** pada graf berarah (*Directed Graph*) menggunakan pewarnaan status tiga warna (*Three-Color Marking*) dan pada graf tak berarah menggunakan pelacakan simpul induk (*Parent Pointer Tracking*).
5. **Menghitung dan Mengisolasi Komponen Terhubung (*Connected Components*)** pada graf tak terhubung (*disconnected graph*) atau hutan graf (*forest*).
6. **Mengevaluasi Karakteristik Memori dan CPU** dari traversal graf untuk mencegah *recursion depth limit* dan *exponential queue growth*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            TEORI GRAF FUNDAMENTAL
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
     STRUKTUR & REPRESENTASI                       PARADIGMA TRAVERSAL
               │                                             │
      ┌────────┴────────┐                           ┌────────┴────────┐
      ▼                 ▼                           ▼                 ▼
Adjacency Matrix   Adjacency List                 BFS                DFS
  O(V²) Space       O(V + E) Space            (Level-Order)       (Deep-Order)
  Dense Graphs      Sparse Graphs                   │                 │
                                            ┌───────┴──────┐   ┌──────┴──────┐
                                            ▼              ▼   ▼             ▼
                                         Queue           Iteratif  Rekursif Tiga Warna
                                      (FIFO State)        (Stack)   (Call-Stack) (Cycle)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Hampir seluruh pemodelan data non-linear di dunia komputasi modern direduksi menjadi persoalan graf. Struktur pohon (*tree*) yang digunakan pada basis data (B-Tree, AST compiler) hanyalah subset terbatas dari graf yang bersifat asiklik dan terhubung.

Ketika batasan hierarki hierarki pohon dihapus—sehingga sebuah simpul (*vertex*) dapat terhubung ke sembarang simpul lain tanpa batasan arah maupun jumlah jalur—kita menghadapi graf:
* **Analisis Jaringan Sosial & Dependency Graph**: Menentukan urutan kompilasi pada sistem *build* modern (Bazel, Cargo, Webpack) atau eksekusi *directed acyclic graph* (DAG) pada mesin *data workflow* (Apache Airflow) membutuhkan pelacakan topologi yang berakar dari DFS.
* **Jaringan Komputer & Routing**: Penentuan jalur paket data (OSPF, BGP), pencarian rute terpendek tak berbobot, dan *peer-to-peer neighbor discovery* beroperasi menggunakan varian BFS.
* **Garbage Collection**: Engine runtime modern (V8, JVM) menggunakan algoritma *tracing garbage collection* (seperti *Mark-and-Sweep*) yang pada intinya adalah traversal graf untuk menemukan simpul objek yang masih dapat dijangkau (*reachable*) dari simpul *Root*.

Tanpa pemahaman yang benar mengenai traversal graf dan representasi memorinya, perangkat lunak yang menangani data berelasi kompleks rentan terhadap jebakan rekursi tak berhingga (*infinite loop* akibat siklus), *Out-of-Memory* (OOM) akibat alokasi matriks yang terlalu besar, atau waktu eksekusi yang meledak menjadi $O(V^2)$ pada graf renggang (*sparse*).

---

## SEKSI 05 — APA ITU (WHAT)

Secara matematis, graf $G$ didefinisikan sebagai pasangan terurut:
$$G = (V, E)$$
di mana:
* $V$ adalah himpunan simpul (*vertices* atau *nodes*).
* $E$ adalah himpunan sisi (*edges* atau *links*), di mana $E \subseteq \{\{u, v\} \mid u, v \in V\}$ untuk graf tak berarah (*undirected*), atau $E \subseteq V \times V$ untuk graf berarah (*directed/digraph*).

### 1. Klasifikasi Graf Berdasarkan Topologi
* **Undirected Graph**: Sisi $(u, v)$ ekuivalen dengan $(v, u)$. Relasi bersifat simetris dua arah.
* **Directed Graph (Digraph)**: Sisi $(u, v)$ menandakan lintasan satu arah dari simpul sumber $u$ menuju target $v$.
* **Weighted vs. Unweighted**: Sisi dapat membawa atribut skalar berupa bobot (*weight/cost* $w(u, v)$) atau murni topologis tanpa bobot.
* **Cyclic vs. Acyclic**: Graf dikatakan *cyclic* jika terdapat lintasan tertutup non-trivial $v_0, v_1, \dots, v_k, v_0$ di mana minimal satu sisi dilalui ulang. Graf tanpa siklus berarah disebut *Directed Acyclic Graph* (DAG).

### 2. Representasi Graf dalam Memori Komputer

#### A. Matriks Ketetanggaan (*Adjacency Matrix*)
Array dua dimensi berukuran $|V| \times |V|$ bertipe boolean atau numerik:
$$A[i][j] = \begin{cases} 1 & \text{jika } (i, j) \in E \\ 0 & \text{lainnya} \end{cases}$$

* **Konsumsi Ruang**: $\Theta(V^2)$ terlepas dari berapa banyak sisi yang ada.
* **Operasi Query Edge $(u, v)$**: $\mathcal{O}(1)$ *lookup* langsung pada indeks memori.
* **Operasi Enumerasi Tetangga Simpul $u$**: $\mathcal{O}(V)$ karena wajib memindai seluruh kolom dari baris $u$.

#### B. Daftar Ketetanggaan (*Adjacency List*)
Struktur data berbasis array berukuran $|V|$, di mana setiap elemen indeks $u$ memegang referensi ke daftar dinamis (vektor/linked list) yang menyimpan simpul-simpul target yang berelasi langsung dengan $u$.

* **Konsumsi Ruang**: $\mathcal{O}(V + E)$ untuk graf berarah, atau $\mathcal{O}(V + 2E)$ untuk graf tak berarah.
* **Operasi Query Edge $(u, v)$**: $\mathcal{O}(\text{degree}(u))$, di mana $\text{degree}(u)$ adalah jumlah tetangga dari $u$.
* **Operasi Enumerasi Tetangga Simpul $u$**: $\mathcal{O}(\text{degree}(u))$, optimal karena langsung membaca memori yang relevan tanpa iterasi kosong.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Algoritma traversal graf mentransformasikan struktur graf non-linear menjadi sekuens linier dari simpul-simpul yang dikunjungi dengan aturan deterministik, memastikan setiap simpul dikunjungi **tepat satu kali** melalui struktur penandaan status (*visited state*).

### 1. Breadth-First Search (BFS)
BFS menjelajahi graf lapis demi lapis (*level-by-level* atau *wavefront expansion*). BFS menjamin bahwa simpul pada jarak $k$ dari simpul awal akan selalu dieksplorasi sebelum simpul pada jarak $k+1$.

* **Struktur Data Dasar**: *Queue* (FIFO - First-In, First-Out).
* **Invarian Operasional**: Antrean selalu berisi simpul yang berjarak $d$ atau $d+1$ dari simpul akar.
* **Karakteristik**:
  * Menemukan jalur terpendek dalam graf tak berbobot (*unweighted shortest path*).
  * Menghabiskan memori sebanding dengan lebar maksimum graf (*maximum width*).

**Langkah-Langkah Eksekusi BFS:**
1. Inisialisasi struktur antrean $Q$ dan himpunan $Visited$.
2. Masukkan simpul awal $s$ ke $Q$, tandai $s$ sebagai telah dikunjungi dalam $Visited$.
3. Selama $Q$ tidak kosong:
   * Keluarkan simpul $u$ dari kepala antrean (*dequeue*).
   * Proses data pada simpul $u$.
   * Untuk setiap tetangga $v$ yang bertetangga dengan $u$:
     * Jika $v \notin Visited$:
       * Tandai $v$ masuk ke $Visited$ **segera saat di-enqueue** (mencegah duplikasi entri dalam antrean).
       * Masukkan $v$ ke bagian belakang $Q$ (*enqueue*).

### 2. Depth-First Search (DFS)
DFS menelusuri cabang graf sedalam mungkin hingga mencapai simpul daun (*dead end*) sebelum melakukan *backtracking* (mundur) ke titik persimpangan terakhir untuk mengeksplorasi jalur alternatif.

* **Struktur Data Dasar**: *Stack* (LIFO - Last-In, First-Out), baik secara eksplisit (alokasi memori heap) maupun implisit (melalui alokasi Call Stack rekursi).
* **Karakteristik**:
  * Penelusuran topologi, komponen terhubung, deteksi siklus, dan artikulasi simpul.
  * Menghabiskan memori sebanding dengan kedalaman maksimum graf (*maximum depth*).

**Klasifikasi Tipe Sisi dalam DFS Forest:**
Saat melakukan DFS, sisi graf terbagi ke dalam empat kategori:
1. **Tree Edge**: Sisi yang membawa traversal ke simpul baru yang belum pernah dikunjungi.
2. **Back Edge**: Sisi yang menghubungkan simpul aktif ke simpul leluhurnya (*ancestor*) yang masih berada di call-stack. **Keberadaan Back Edge pada graf berarah adalah penanda mutlak adanya siklus (*cycle*)!**
3. **Forward Edge**: Sisi yang menghubungkan simpul aktif ke keturunannya (*descendant*) yang sudah selesai diproses.
4. **Cross Edge**: Sisi yang menghubungkan dua simpul yang tidak memiliki relasi leluhur langsung (berada di sub-cabang pohon DFS yang berbeda).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Representasi Graf Fisik vs. Memori

Diberikan sebuah graf berarah dengan 4 simpul ($V = \{0, 1, 2, 3\}$):

```
       ┌───────┐
       │   0   │──────┐
       └───────┘      │
         │   ▲        │
         │   │        │
         ▼   │        ▼
       ┌───────┐    ┌───────┐
       │   1   │───▶│   2   │
       └───────┘    └───────┘
         │            ▲
         ▼            │
       ┌───────┐      │
       │   3   │──────┘
       └───────┘
```

#### A. Representasi Matriks Ketetanggaan (4x4)
```
          Target (j)
         0   1   2   3
       ┌───┬───┬───┬───┐
     0 │ 0 │ 1 │ 1 │ 0 │  -> Memori kontinu: 16 blok primitif
       ├───┼───┼───┼───┤
 S   1 │ 1 │ 0 │ 1 │ 1 │  -> Query (1, 2)? Akses M[1][2] = 1 (O(1))
 u   ├───┼───┼───┼───┤
 m   2 │ 0 │ 0 │ 0 │ 0 │  -> Baris simpul 2 kosong (Out-degree = 0)
 b   ├───┼───┼───┼───┤
 (i) 3 │ 0 │ 0 │ 1 │ 0 │
       └───┴───┴───┴───┘
```

#### B. Representasi Daftar Ketetanggaan
```
 Indeks Array
 ┌───────┐
 │   0   │ ──▶ [ 1 ] ──▶ [ 2 ] ──▶ NULL
 ├───────┤
 │   1   │ ──▶ [ 0 ] ──▶ [ 2 ] ──▶ [ 3 ] ──▶ NULL
 ├───────┤
 │   2   │ ──▶ NULL
 ├───────┤
 │   3   │ ──▶ [ 2 ] ──▶ NULL
 └───────┘
```

### 2. State Machine Traversal BFS vs DFS

Diberikan Graf:
```
           ( A )
          /     \
        ( B )   ( C )
        /   \       \
      ( D ) ( E )   ( F )
```

#### A. Alur BFS (Queue State Transformation)
```
 Langkah   Current Pop   Antrean (Queue) pasca Operasi      Visited Set
 ────────────────────────────────────────────────────────────────────────────
  0        -             [ A ]                              { A }
  1        A             [ B, C ]                           { A, B, C }
  2        B             [ C, D, E ]                        { A, B, C, D, E }
  3        C             [ D, E, F ]                        { A, B, C, D, E, F }
  4        D             [ E, F ]                           { A, B, C, D, E, F }
  5        E             [ F ]                              { A, B, C, D, E, F }
  6        F             [ ]                                { A, B, C, D, E, F }

 Pola Urutan: A -> B -> C -> D -> E -> F (Eksplorasi Per Level Horisontal)
```

#### B. Alur DFS (Call Stack Transformation)
```
 Call Stack (Tumbuh ke Bawah):
 
 Frame 0:   dfs(A)
             ├── Frame 1: dfs(B)
             │             ├── Frame 2: dfs(D) -> Dead end, Pop Frame 2
             │             └── Frame 3: dfs(E) -> Dead end, Pop Frame 3
             │             Pop Frame 1
             └── Frame 4: dfs(C)
                           └── Frame 5: dfs(F) -> Dead end, Pop Frame 5
                           Pop Frame 4
             Pop Frame 0

 Pola Urutan: A -> B -> D -> E -> C -> F (Eksplorasi Mendalam Vertikal)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi struktur graf berbasis Adjacency List dan traversal fundamental menggunakan Python 3.11+.

```python
from collections import deque
from typing import Dict, List, Set, Optional


class Graph:
    """Implementasi Graf tak berbobot menggunakan representasi Adjacency List."""

    def __init__(self, directed: bool = False) -> None:
        self.adj_list: Dict[str, List[str]] = {}
        self.directed: bool = directed

    def add_vertex(self, vertex: str) -> None:
        """Menambahkan simpul baru ke dalam graf jika belum terdaftar."""
        if vertex not in self.adj_list:
            self.adj_list[vertex] = []

    def add_edge(self, u: str, v: str) -> None:
        """
        Menambahkan sisi antara simpul u dan v.
        Secara otomatis mendaftarkan simpul jika belum ada.
        """
        self.add_vertex(u)
        self.add_vertex(v)
        
        self.adj_list[u].append(v)
        if not self.directed:
            self.adj_list[v].append(u)

    def bfs(self, start_node: str) -> List[str]:
        """
        Melakukan traversal Breadth-First Search dari start_node.
        Time Complexity: O(V + E)
        Space Complexity: O(V)
        """
        if start_node not in self.adj_list:
            return []

        visited: Set[str] = set()
        queue: deque[str] = deque()
        traversal_order: List[str] = []

        # Inisialisasi start_node
        visited.add(start_node)
        queue.append(start_node)

        while queue:
            current_vertex = queue.popleft()
            traversal_order.append(current_vertex)

            for neighbor in self.adj_list[current_vertex]:
                if neighbor not in visited:
                    # KRITIKAL: Tandai visited saat enqueue untuk mencegah duplikasi
                    visited.add(neighbor)
                    queue.append(neighbor)

        return traversal_order

    def dfs_iterative(self, start_node: str) -> List[str]:
        """
        Melakukan traversal Depth-First Search secara iteratif menggunakan LIFO Stack.
        Time Complexity: O(V + E)
        Space Complexity: O(V)
        """
        if start_node not in self.adj_list:
            return []

        visited: Set[str] = set()
        stack: List[str] = [start_node]
        traversal_order: List[str] = []

        while stack:
            current_vertex = stack.pop()

            if current_vertex not in visited:
                visited.add(current_vertex)
                traversal_order.append(current_vertex)

                # Masukkan tetangga ke stack dengan urutan terbalik
                # agar tetangga pertama diproses terlebih dahulu
                for neighbor in reversed(self.adj_list[current_vertex]):
                    if neighbor not in visited:
                        stack.append(neighbor)

        return traversal_order

    def dfs_recursive(self, start_node: str) -> List[str]:
        """Fungsi wrapper untuk mengeksekusi DFS rekursif."""
        visited: Set[str] = set()
        traversal_order: List[str] = []

        def _dfs_helper(vertex: str) -> None:
            visited.add(vertex)
            traversal_order.append(vertex)

            for neighbor in self.adj_list[vertex]:
                if neighbor not in visited:
                    _dfs_helper(neighbor)

        if start_node in self.adj_list:
            _dfs_helper(start_node)

        return traversal_order


# Verifikasi Eksekusi Sederhana
if __name__ == "__main__":
    g = Graph(directed=False)
    g.add_edge("A", "B")
    g.add_edge("A", "C")
    g.add_edge("B", "D")
    g.add_edge("B", "E")
    g.add_edge("C", "F")

    print(f"BFS Order: {g.bfs('A')}")
    # Output yang diharapkan: ['A', 'B', 'C', 'D', 'E', 'F']

    print(f"DFS Iterative Order: {g.dfs_iterative('A')}")
    # Output yang diharapkan: ['A', 'B', 'D', 'E', 'C', 'F']

    print(f"DFS Recursive Order: {g.dfs_recursive('A')}")
    # Output yang diharapkan: ['A', 'B', 'D', 'E', 'C', 'F']
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

**Kasus Nyata**: Resolver Dependensi Service Infrastruktur & Deteksi Siklus (*Deadlock Prevention*).

Dalam arsitektur mikroservis atau sistem kontainer (*orchestrator*), layanan-layanan saling bergantung saat *booting*. Jika Service A membutuhkan Service B, dan Service B membutuhkan Service C, namun Service C membutuhkan Service A, terjadi *circular dependency*. Sistem akan membeku (*deadlock*). Kita menggunakan algoritma **DFS Three-Color Marking** (White, Gray, Black) untuk mendeteksi siklus dan mencatat lintasan penyebab kegagalan secara deterministik.

* Status Penandaan:
  * **WHITE (0)**: Simpul belum pernah dieksplorasi sama sekali.
  * **GRAY (1)**: Simpul sedang berada dalam Call Stack rekursi aktif (ancestor aktif). Jika kita menemukan tetangga berstatus GRAY, **siklus terdeteksi**.
  * **BLACK (2)**: Simpul beserta seluruh anak cabangnya telah selesai diproses sepenuhnya.

```python
from enum import Enum
from typing import Dict, List, Optional, Tuple


class NodeState(Enum):
    WHITE = 0  # Unvisited
    GRAY = 1   # Visiting (Currently in Call Stack)
    BLACK = 2  # Visited & Fully Resolved


class ServiceDependencyResolver:
    """
    Dependency engine kelas produksi untuk memvalidasi keamanan DAG 
    sebelum deployment layanan infrastruktur.
    """

    def __init__(self) -> None:
        self.adj_list: Dict[str, List[str]] = {}

    def register_dependency(self, service: str, depends_on: str) -> None:
        """
        Mendaftarkan relasi: `service` membutuhkan `depends_on`.
        Arah Sisi Graf: service -> depends_on
        """
        if service not in self.adj_list:
            self.adj_list[service] = []
        if depends_on not in self.adj_list:
            self.adj_list[depends_on] = []
        self.adj_list[service].append(depends_on)

    def find_circular_dependency(self) -> Optional[List[str]]:
        """
        Menganalisis dependensi menggunakan DFS Three-Color Algorithm.
        
        Returns:
            Optional[List[str]]: Mengembalikan urutan siklus jika terdeteksi,
                                 atau None jika graf aman (bersifat DAG murni).
        """
        states: Dict[str, NodeState] = {node: NodeState.WHITE for node in self.adj_list}
        parent_map: Dict[str, Optional[str]] = {node: None for node in self.adj_list}
        cycle_path: List[str] = []

        def _dfs_cycle_check(current: str) -> bool:
            states[current] = NodeState.GRAY

            for neighbor in self.adj_list[current]:
                if states[neighbor] == NodeState.GRAY:
                    # Siklus Ditemukan! Lakukan rekonstruksi jejak siklus (Back Edge).
                    cycle_path.append(neighbor)
                    trace = current
                    while trace != neighbor and trace is not None:
                        cycle_path.append(trace)
                        trace = parent_map[trace]
                    cycle_path.append(neighbor)
                    cycle_path.reverse()
                    return True

                if states[neighbor] == NodeState.WHITE:
                    parent_map[neighbor] = current
                    if _dfs_cycle_check(neighbor):
                        return True

            states[current] = NodeState.BLACK
            return False

        # Iterasi seluruh simpul untuk menangani graf yang terputus (disconnected components)
        for service in self.adj_list:
            if states[service] == NodeState.WHITE:
                if _dfs_cycle_check(service):
                    return cycle_path

        return None


# Driver Verifikasi
if __name__ == "__main__":
    resolver = ServiceDependencyResolver()

    # Skenario: Arsitektur Valid
    # Auth-Service -> Database
    # API-Gateway -> Auth-Service
    resolver.register_dependency("API-Gateway", "Auth-Service")
    resolver.register_dependency("Auth-Service", "Database")

    cycle = resolver.find_circular_dependency()
    assert cycle is None, "Harusnya aman tanpa siklus"
    print("[PASS] Verifikasi Graf Tanpa Siklus: Sukses.")

    # Skenario: Injeksi Circular Dependency
    # Database secara ilegal mereferensikan API-Gateway (misal melalui webhook synchronous)
    resolver.register_dependency("Database", "API-Gateway")

    cycle = resolver.find_circular_dependency()
    if cycle:
        print("[CRITICAL ALERT] Circular Dependency terdeteksi!")
        print(f"Jalur Siklus: {' -> '.join(cycle)}")
    
    # Expected output:
    # Jalur Siklus: API-Gateway -> Auth-Service -> Database -> API-Gateway
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih antara jenis representasi graf dan algoritma traversal merupakan keputusan rekayasa sistem yang melibatkan kompromi eksplisit antara *footprint* memori, latensi komputasi, dan karakteristik topologi data.

### 1. Matrix vs. Adjacency List

| Karakteristik | Adjacency Matrix | Adjacency List | Pertimbangan Rekayasa |
| :--- | :--- | :--- | :--- |
| **Space Complexity** | $\Theta(V^2)$ | $\Theta(V + E)$ | Matriks memboroskan memori pada graf renggang (*sparse graph* di mana $E \ll V^2$). Gunakan matriks hanya bila graf sangat padat (*dense*, $E \approx V^2$) atau bila $V$ berukuran kecil dan tetap ($V \le 1000$). |
| **Edge Lookup $(u, v)$** | $\mathcal{O}(1)$ | $\mathcal{O}(\text{degree}(u))$ | Jika aplikasi Anda didominasi oleh operasi verifikasi relasi spesifik antar pasangan entitas acak, matriks lebih unggul. |
| **Iterasi Seluruh Tetangga** | $\Theta(V)$ | $\Theta(\text{degree}(u))$ | Matriks mewajibkan pemindaian loop kosong jika banyak simpul berderajat nol. Adjacency list memproses data secara optimal sesuai eksistensi relasi. |
| **Locality of Reference** | Sangat Tinggi (Array 2D planar) | Rendah (Pointer indirection / Array of lists) | Matriks memiliki *cache-locality* tinggi pada level hardware jika diakses secara *row-major order*. |

### 2. BFS vs. DFS

| Dimensi Evaluasi | Breadth-First Search (BFS) | Depth-First Search (DFS) |
| :--- | :--- | :--- |
| **Struktur Memori** | Queue (FIFO) | Stack (LIFO / Call Stack) |
| **Kompleksitas Ruang** | $\mathcal{O}(\text{Width}_{\text{max}}) \approx \mathcal{O}(V)$ | $\mathcal{O}(\text{Depth}_{\text{max}}) \approx \mathcal{O}(V)$ |
| **Shortest Path** | **Dijamin optimal** untuk graf tak berbobot (*unweighted*). | **Tidak menjamin** jalur terpendek; menemukan sembarang lintasan yang valid. |
| **Perilaku Memori Ekstrem** | Rentan ledakan memori pada graf dengan *branching factor* tinggi (contoh: simpul dengan ratusan anak langsung memenuhi antrean). | Rentan terhadap bahaya *Stack Overflow* pada graf dengan rantai linear panjang jika diimplementasikan secara rekursif murni. |
| **Kasus Penggunaan Utama** | Jarak minimum, pencarian koneksi derajat ke-$N$ (contoh: LinkedIn *degrees of connection*), *flood fill* berbasis radius. | Deteksi siklus, pengurutan topologis (*Topological Sort*), komponen terhubung kuat (*SCC*), pencarian solusi labirin / *backtracking*. |

---

## SEKSI 11 — BEST PRACTICES

1. **Tandai Visited Segera Saat Enqueue (BFS Rule)**:
   * **Salah**: Menandai simpul sebagai *visited* saat simpul di-*dequeue*. Hal ini akan menyebabkan simpul yang sama dimasukkan berulang kali ke dalam antrean oleh tetangga-tetangganya pada level yang sama, menghasilkan ledakan ukuran memori secara eksponensial ($\mathcal{O}(b^d)$ duplikat).
   * **Benar**: Tandai simpul sebagai *visited* tepat sebelum atau sesaat setelah operasi *enqueue* dilakukan.

2. **Gunakan Deque Khusus untuk Antrean**:
   * Jangan gunakan tipe `list` standar Python sebagai antrean dengan memanggil `list.pop(0)`. Operasi ini memiliki kompleksitas $\mathcal{O}(N)$ karena seluruh elemen harus digeser di memori.
   * Gunakan `collections.deque` yang berbasis blok memori ganda (*doubly-linked chunks*) dengan penjaminan kompleksitas $\mathcal{O}(1)$ untuk operasi `popleft()`.

3. **Gunakan Pendekatan Iteratif untuk DFS Skala Produksi**:
   * Rekursi bawaan bahasa pemrograman dibatasi oleh batas tumpukan panggilan (*call stack limit*, default Python: 1000 frame).
   * Pada graf dengan kedalaman jutaan simpul (misalnya rantai *unbalanced linear graph*), DFS rekursif akan memicu `RecursionError: maximum recursion depth exceeded`. Gunakan tumpukan eksplisit (*explicit heap-allocated stack*).

4. **Pertimbangkan Penyimpanan Status Berbasis Bitset**:
   * Pada graf dengan simpul berupa integer berkisar $0 \dots V-1$, alokasi `std::vector<bool>` (C++) atau `bytearray` (Python) jauh lebih efisien dalam alokasi cache prosesor daripada `std::unordered_set` atau `set()` Python yang sarat beban *hashing overhead*.

5. **Penanganan Graf Tak Terhubung (*Disconnected Graphs*)**:
   * Selalu bungkus traversal di dalam loop eksternal yang memindai semua $v \in V$. Traversal tunggal hanya akan memproses komponen simpul asal, dan akan gagal memproses simpul pulau (*isolated clusters*).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Missing Visited Mutation on Enqueue (The Memory Explosion)
```python
# KODE SALAH
while queue:
    curr = queue.popleft()
    visited.add(curr)  # TERLAMBAT! Simpul yang sama sudah antre berkali-kali
    for neighbor in graph[curr]:
        if neighbor not in visited:
            queue.append(neighbor)

# KODE BENAR
while queue:
    curr = queue.popleft()
    for neighbor in graph[curr]:
        if neighbor not in visited:
            visited.add(neighbor)  # AMANKAN SEGERA
            queue.append(neighbor)
```

### 2. Ambigu Identifikasi Siklus pada Graf Tak Berarah
Pada graf berarah, melihat simpul tetangga yang telah dikunjungi belum tentu menunjukkan adanya siklus jika simpul tersebut adalah simpul induk langsung yang baru saja memanggil simpul saat ini.
* **Solusi**: Traversal harus selalu meneruskan parameter `parent`. Abaikan simpul tetangga jika `neighbor == parent`. Jika tetangga telah dikunjungi dan `neighbor != parent`, maka siklus valid ditemukan.

### 3. Mengasumsikan Bobot Sama dengan Jumlah Sisi
Menggunakan BFS untuk mencari lintasan terpendek pada graf yang memiliki **bobot variatif** (*weighted graph*) adalah cacat logika fundamental.
* BFS hanya menjamin jalur terpendek jika seluruh sisi memiliki bobot seragam ($w(e) = c, \forall e \in E$). Untuk graf berbobot positif non-seragam, gunakan Algoritma Dijkstra.

### 4. Mutasi Adjacency List Saat Iterasi
Menghapus atau menyisipkan simpul/sisi langsung ke dalam struktur `adj_list` saat sedang melakukan iterasi traversal akan merusak *internal iterator state* dan menghasilkan *undefined behavior* atau `RuntimeError: dictionary changed size during iteration`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Deteksi Graf Bipartit (Level: Mudah)
* **Tantangan**: Buat fungsi `is_bipartite(graph: Dict[int, List[int]]) -> bool`. Sebuah graf dikatakan bipartit jika himpunan simpulnya dapat dibagi menjadi dua kelompok independen $U$ dan $V$ sedemikian rupa sehingga setiap sisi menghubungkan simpul di $U$ ke simpul di $V$ (graf dapat diwarnai menggunakan 2 warna tanpa ada 2 simpul bertetangga dengan warna sama).
* **Batasan**: Graf tak berarah, bisa memiliki komponen terputus. $|V| \le 10^4$.
* **Hint**: Gunakan BFS/DFS dengan array penanda warna (`0` = belum diwarnai, `1` = merah, `-1` = biru).

### Latihan 2: Menghitung Jumlah Pulau Jaringan (Level: Menengah)
* **Tantangan**: Diberikan matriks grid 2D $M \times N$ berisi `'1'` (koneksi aktif) dan `'0'` (koneksi kosong). Sebuah pulau didefinisikan sebagai kumpulan simpul `'1'` yang terhubung secara horizontal maupun vertikal. Hitung total jumlah pulau terisolasi di dalam matriks.
* **Batasan**: $M, N \le 300$. Manipulasi matriks langsung diizinkan untuk menghemat ruang memori.
* **Hint**: Iterasi setiap koordinat $(r, c)$. Jika ditemukan `'1'`, picu DFS/BFS untuk menenggelamkan (*sink*) seluruh simpul terhubung menjadi `'0'`, lalu inkrementasi counter pulau.

### Latihan 3: Jalur Terpendek Labirin dengan Penghalang Kunci (Level: Sulit)
* **Tantangan**: Diberikan peta grid berukuran $R \times C$. Karakter `'S'` adalah titik awal, `'E'` adalah pintu keluar, `'#'` adalah tembok, `'.'` adalah jalan kosong, dan huruf kecil `'a'`, `'b'`, `'c'` adalah kunci yang membuka pintu berhuruf kapital `'A'`, `'B'`, `'C'`. Temukan jumlah langkah minimum dari `'S'` ke `'E'`.
* **Batasan**: Maksimal kunci unik adalah 6 ($a \dots f$). $R, C \le 50$.
* **Hint**: BFS standard dengan *state tracking* yang diperluas: `(row, col, key_bitmask)`. Simpul pada graf implisit ini bukan hanya koordinat, tetapi kombinasi koordinat dan status kunci yang dimiliki dalam bentuk bitmask.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Diberikan graf terhubung tak berarah dengan $|V|$ simpul dan $|E|$ sisi. Berapa jumlah minimum dan maksimum sisi yang mungkin ada?**
   * A. Min: $0$, Max: $|V|$
   * B. Min: $|V| - 1$, Max: $\frac{|V|(|V|-1)}{2}$
   * C. Min: $|V|$, Max: $|V|^2$
   * D. Min: $1$, Max: $|E| \times |V|$
   * *Jawaban*: **B**. Graf terhubung minimal adalah pohon (*tree*) yang memiliki $|V| - 1$ sisi. Batas maksimum pada graf sederhana tak berarah adalah kombinasi $\binom{|V|}{2} = \frac{|V|(|V|-1)}{2}$.

2. **Apa yang terjadi jika penandaan `visited.add(neighbor)` pada algoritma BFS diletakkan saat simpul dikeluarkan dari antrean (`queue.popleft()`), bukan saat dimasukkan (`queue.append()`)?**
   * A. Traversal akan otomatis berubah menjadi DFS.
   * B. Tidak ada perbedaan, performa dan konsumsi memori identik.
   * C. Algoritma mengalami kegagalan memori akibat entri simpul yang identik masuk ke antrean berkali-kali secara redundan.
   * D. Hasil urutan penelusuran traversal menjadi terbalik.
   * *Jawaban*: **C**. Simpul tetangga yang sama dapat diekspansi oleh banyak simpul pada level yang sama sebelum simpul tersebut sempat di-*pop*, memicu redundansi komputasi dan ledakan memori masif.

3. **Manakah dari jenis sisi (*edge*) berikut dalam DFS Forest pada graf berarah yang secara definitif membuktikan adanya siklus (*cycle*)?**
   * A. Tree Edge
   * B. Cross Edge
   * C. Forward Edge
   * D. Back Edge
   * *Jawaban*: **D**. Back Edge mengarah dari simpul saat ini kembali ke simpul leluhurnya (*ancestor*) yang status eksekusinya masih aktif di dalam Call Stack, menandakan adanya lintasan tertutup (siklus).

4. **Kapan implementasi Adjacency Matrix lebih direkomendasikan daripada Adjacency List?**
   * A. Ketika graf memiliki sangat sedikit sisi ($|E| \approx |V|$).
   * B. Ketika graf sangat padat ($|E| \approx |V|^2$) dan program membutuhkan pengecekan eksistensi sisi $(u, v)$ secara ultra-cepat $\mathcal{O}(1)$.
   * C. Ketika algoritma yang digunakan adalah BFS, bukan DFS.
   * D. Ketika graf memiliki bobot sisi yang bernilai negatif.
   * *Jawaban*: **B**. Matriks memanfaatkan efisiensi ruang saat sisi mendekati kapasitas maksimum ($V^2$), memangkas *overhead* pointer dari linked list atau vektor dinamis, serta memberikan lookup instan $\mathcal{O}(1)$.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C.** (2022). *Introduction to Algorithms* (4th ed.). MIT Press.
   * *Bab 22: Elementary Graph Algorithms* (Halaman 589–620). Wajib dibaca untuk analisis formal Teorema White-Path dan klasifikasi sisi DFS.
2. **Sedgewick, R., & Wayne, K.** (2011). *Algorithms* (4th ed.). Addison-Wesley Professional.
   * *Bab 4: Graphs* (Graph data types, DFS/BFS implementations and invariants).
3. **Tarjan, R. E.** (1972). *Depth-First Search and Linear Graph Algorithms*. SIAM Journal on Computing, 1(2), 146-160.
   * Paper fundamental yang meletakkan dasar matematis modern bagi pemanfaatan DFS dalam analisis topologi dan pemisahan komponen graf.
4. **Kleinberg, J., & Tardos, É.** (2006). *Algorithm Design*. Pearson.
   * *Bab 3: Graphs* (Representasi graf praktis dan teknik penelusuran status).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    RINGKASAN TEKNIKAL TRAVERSAL GRAF                       │
├───────────────────┬────────────────────────────┬───────────────────────────┤
│ Atribut           │ Breadth-First Search (BFS) │ Depth-First Search (DFS)  │
├───────────────────┼────────────────────────────┼───────────────────────────┤
│ Mekanisme Dasar   │ FIFO (Queue)               │ LIFO (Stack / Call Stack) │
│ Pola Gerak        │ Ekspansi Konsentris/Level  │ Penelusuran Vertikal Dalam│
│ Unweighted Path   │ Menjamin Lintasan Terpendek│ Tidak Menjamin Terpendek  │
│ Kompleksitas Waktu│ O(V + E)                   │ O(V + E)                  │
│ Kompleksitas Ruang│ O(V) [Faktor Lebar/Width]  │ O(V) [Faktor Dalam/Depth] │
│ Indikator Siklus  │ Deteksi Cross/Back Level   │ Back Edge ke Ancestor Aktif│
│ Representasi Utama│ Adjacency List (Sparse)    │ Adjacency Matrix (Dense)  │
└───────────────────┴────────────────────────────┴───────────────────────────┘
```

Pondasi utama graf berakar pada pemahaman cara merepresentasikan relasi secara efisien di memori dan bagaimana mengarungi simpul-simpul tersebut tanpa terjebak dalam redundansi pemrosesan. BFS dan DFS bukan sekadar algoritma traversal; keduanya adalah cetak biru (*blueprint*) dari algoritma lanjutan seperti Dijkstra, Prim, Kruskal, Topological Sort, Kosaraju, dan Tarjan.

---

## SEKSI 17 — GLOSARIUM

* **Adjacency List**: Koleksi daftar atau larik dinamis di mana indeks baris memetakan simpul asal ke simpul-simpul tujuan yang terhubung langsung.
* **Adjacency Matrix**: Larik dua dimensi berukuran $|V| \times |V|$ di mana setiap sel boolean $[u][v]$ mengindikasikan keberadaan sisi dari $u$ ke $v$.
* **Back Edge**: Sisi yang mengarah dari simpul saat ini kembali ke simpul leluhurnya pada tumpukan eksekusi DFS aktif; bukti keberadaan siklus.
* **Breadth-First Search (BFS)**: Traversal tingkat-demi-tingkat yang memprioritaskan penelusuran seluruh tetangga horizontal terdekat sebelum memperdalam level.
* **Depth-First Search (DFS)**: Traversal eksplorasi mendalam yang memprioritaskan penelusuran sepanjang cabang individual hingga simpul buntu tercapai sebelum melakukan *backtrack*.
* **Directed Acyclic Graph (DAG)**: Graf berarah tanpa siklus tertutup, fondasi struktural pemodelan ketergantungan tugas (*task dependency*).
* **Sparse Graph**: Graf yang memiliki jumlah sisi jauh lebih sedikit dari kapasitas maksimum teoritisnya ($|E| \ll |V|^2$).
* **Dense Graph**: Graf yang memiliki jumlah sisi mendekati kapasitas maksimum batas kuadratiknya ($|E| \approx |V|^2$).
* **Degree**: Jumlah sisi yang menyentuh simpul tertentu. Pada digraph, terbagi menjadi *In-Degree* (panah masuk) dan *Out-Degree* (panah keluar).

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Jebakan Mental Peserta**: Mahasiswa sering mengira graf dan *tree* adalah topik yang terpisah. Tekankan sejak awal bahwa: *Tree is just a restricted DAG with 1 root and single parents*. Memahami konsep graf akan mempermudah topik struktur data lainnya.
* **Visualisasi Debugging**: Saat mengajar secara tatap muka atau live-coding, selalu paksa peserta didik untuk menggambar tabel `Visited`, isi antrean `Queue`, dan `Call Stack` di atas kertas atau whiteboard. Menulis kode graf tanpa pemahaman visualisasi status pointer adalah penyebab utama *logic bug*.
* **Penekanan Bahasa**: Dalam Python, perhatikan penggunaan memori internal `set` dan `deque`. Tunjukkan profiling memori langsung antara penggunaan `list.pop(0)` versus `deque.popleft()` pada data $10^5$ simpul untuk membuktikan pentingnya kompleksitas struktural secara empiris.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023)**:
  * Inisialisasi rilis kurikulum modul standar `DSA-01-06-01`.
  * Penambahan arsitektur implementasi Adjacency List dan DFS Tiga Warna.
  * Standarisasi format 20 seksi teknis komprehensif.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* ◄ **Modul Sebelumnya**: `DSA-01-05-02: Advanced Trees — Trie, AVL, & Red-Black Tree Implementation`
* ► **Modul Berikutnya**: `DSA-01-06-02: Graph Applications — Topological Sort & Disjoint Set Union (DSU)`