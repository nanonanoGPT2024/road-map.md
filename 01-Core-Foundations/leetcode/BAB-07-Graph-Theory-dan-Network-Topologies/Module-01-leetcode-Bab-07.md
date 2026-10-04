## SEKSI 01 — IDENTITAS MODUL

* **Track/Curriculum:** LeetCode & Algorithmic Problem Solving
* **Kategori:** 01-Core-Foundations
* **Bab:** 07 — Graph Theory & Network Topologies
* **Modul:** 01 — Fundamental Graph Representations & Topologies
* **Tingkat Kesulitan:** Intermediate
* **Estimasi Waktu Penyelesaian:** 120–150 menit
* **Prasyarat:** Pemahaman Array/List, Hash Map, Set, Rekursi, dan Pointer/Referensi

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Mendefinisikan** komponen formal graf ($G = (V, E)$), karakteristik struktural (directed, undirected, weighted, unweighted, cyclic, acyclic), serta batas teoritis kardinalitas edge terhadap vertex ($|E| \le |V|^2$).
2. **Mengimplementasikan dan Memilih** struktur representasi graf yang optimal (Adjacency Matrix, Adjacency List, Edge List, Implicit Grid Graph) berdasarkan batasan waktu (*time limit*) dan memori (*space limit*) LeetCode.
3. **Menganalisis Trade-off** kompleksitas waktu dan ruang untuk operasi-operasi dasar graf: pemeriksaan ketetanggaan (*edge lookup*), iterasi tetangga (*neighbor iteration*), penambahan/penghapusan simpul dan sisi.
4. **Menerjemahkan** representasi input standar LeetCode (seperti `edges: List[List[int]]` atau `grid: List[List[str]]`) ke dalam struktur data traversal yang efisien tanpa alokasi memori berlebih.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                               Graph G = (V, E)
                                      |
         +----------------------------+----------------------------+
         |                                                         |
  Karakteristik Topologi                                  Representasi Data
         |                                                         |
  +------+------+------+                                    +------+------+------+
  |             |      |                                    |             |      |
Direction   Cycles  Weights                           Adjacency      Adjacency  Implicit
  |             |      |                                Matrix         List      Grid
  +-- Directed  +-- DAG+-- Weighted                         |             |      |
  +-- Undirected+-- DCG+-- Unweighted                     Dense         Sparse   2D-Matrix
                                                          O(V^2)        O(V+E)   Implicit E
```

* **Vertex ($V$) & Edge ($E$):** Simpul sebagai entitas independen dan sisi sebagai relasi biner antar simpul.
* **Topologi Jaringan:** Directed Graph (Digraph), Undirected Graph, Directed Acyclic Graph (DAG), Bipartite Graph, Tree (Connected Acyclic Undirected Graph).
* **Derajat Simpul (*Degree*):** Degree pada graf tak berarah; *In-Degree* dan *Out-Degree* pada graf berarah.
* **Handshaking Lemma:** $\sum_{v \in V} \deg(v) = 2|E|$.
* **Representasi Fisik vs Abstrak:** Explicit storage (Array of vectors, Map of lists, Matrix) vs Implicit storage (Grid coordinate offsets, State transitions).

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Graf adalah abstraksi universal untuk memodelkan hubungan non-linear antar entitas. Di platform seperti LeetCode:
1. **Pondasi Algoritma Lanjutan:** Traversal (BFS/DFS), Topological Sort, Shortest Path (Dijkstra, Bellman-Ford), Minimum Spanning Tree (Kruskal, Prim), hingga Network Flow bergantung 100% pada pemilihan representasi graf yang tepat.
2. **Implikasi Kompleksitas Memori:** Menggunakan Adjacency Matrix berukuran $V \times V$ ketika $V = 10^5$ akan langsung memicu *Memory Limit Exceeded* (MLE) karena membutuhkan alokasi memori sebesar $\approx 10^{10} \times 4\text{ bytes} \approx 40\text{ GB}$.
3. **Transformasi Masalah Abstrak:** Banyak problem LeetCode yang tampak seperti puzzle string (Word Ladder), simulasi matriks (Number of Islands), atau penjadwalan (Course Schedule) yang sejatinya adalah pemodelan graf terselubung.

---

## SEKSI 05 — APA ITU (WHAT)

Graf $G$ secara formal didefinisikan sebagai pasangan terurut $G = (V, E)$, di mana:
* $V$ adalah himpunan simpul (*vertices* atau *nodes*).
* $E \subseteq V \times V$ adalah himpunan sisi (*edges*) yang menghubungkan pasangan simpul.

### Taksonomi Topologi Graf

1. **Undirected Graph:** Relasi bersifat simetris. Sisi $(u, v)$ identik dengan $(v, u)$. Derajat suatu simpul $\deg(v)$ adalah jumlah sisi yang terhubung ke $v$.
2. **Directed Graph (Digraph):** Relasi memiliki arah. Sisi $(u, v)$ mengindikasikan koneksi dari $u$ menuju $v$.
   * $\text{in-degree}(v) = |\{u \in V \mid (u, v) \in E\}|$
   * $\text{out-degree}(v) = |\{w \in V \mid (v, w) \in E\}|$
3. **Weighted Graph:** Setiap sisi $e \in E$ diasosiasikan dengan fungsi bobot $w: E \to \mathbb{R}$.
4. **Graph Density:**
   * **Sparse Graph:** $|E| \ll |V|^2$, umumnya $|E| \approx O(|V|)$.
   * **Dense Graph:** $|E| \approx |V|^2$.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Representasi graf menentukan bagaimana data relasional dialokasikan di dalam memori komputer.

### 1. Adjacency Matrix
Matriks boolean atau numerik $A$ berukuran $|V| \times |V|$:
$$A[u][v] = \begin{cases} 1 \text{ (atau } w\text{)}, & \text{jika } (u, v) \in E \\ 0 \text{ (atau } \infty\text{)}, & \text{lainnya} \end{cases}$$

* **Karakteristik Memori:** Membutuhkan alokasi memori kontigu statis berukuran $\Theta(|V|^2)$.
* **Pencarian Sisi:** Operasi $(u, v) \in E$ diselesaikan dalam $O(1)$ waktu akses langsung.
* **Iterasi Tetangga:** Membutuhkan pemindaian sepanjang baris $u$, memakan waktu $\Theta(|V|)$.

### 2. Adjacency List
Array atau Hash Map berukuran $|V|$, di mana setiap elemen menyimpan daftar simpul tetangga yang terhubung langsung:
$$\text{Adj}[u] = \{v \in V \mid (u, v) \in E\}$$

* **Karakteristik Memori:** Mengalokasikan memori dinamis proporsional terhadap ukuran data: $\Theta(|V| + |E|)$.
* **Pencarian Sisi:** Memerlukan pemindaian linear dalam daftar tetangga: $O(\deg(u))$. Jika tetangga disimpan dalam Hash Set, kompleksitasnya menjadi $O(1)$ rata-rata.
* **Iterasi Tetangga:** Membutuhkan waktu optimal $O(\deg(u))$.

### 3. Edge List
Struktur data datar berisi kumpulan tupel:
$$E = \{(u, v, w_1), (x, y, w_2), \dots\}$$

* Sangat efisien untuk algoritma yang memproses sisi secara global tanpa memerlukan traversal tetangga lokal secara acak (misalnya Kruskal's MST atau Bellman-Ford).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Perbandingan Fisik Representasi Graf

Diberikan Directed Weighted Graph dengan $V = \{0, 1, 2, 3\}$:

```text
       (0) -------[ 5 ]-------> (1)
        |                        |
      [ 2 ]                    [ 1 ]
        |                        |
        v                        v
       (3) <------[ 4 ]-------- (2)
```

#### Struktur 1: Adjacency Matrix
Tabel berukuran $4 \times 4$ (nilai `INF` merepresentasikan ketiadaan sisi):

```text
       0      1      2      3
    +------+------+------+------+
 0  |  0   |  5   | INF  |  2   |
    +------+------+------+------+
 1  | INF  |  0   |  1   | INF  |
    +------+------+------+------+
 2  | INF  | INF  |  0   |  4   |
    +------+------+------+------+
 3  | INF  | INF  | INF  |  0   |
    +------+------+------+------+
```

#### Struktur 2: Adjacency List (Vector of Vectors/Pairs)
Pointer/Array dari daftar dinamis:

```text
 [Index]   Head -> Elements [Target Node, Weight]
  Index 0: [ (1, 5) ] -> [ (3, 2) ] -> null
  Index 1: [ (2, 1) ] -> null
  Index 2: [ (3, 4) ] -> null
  Index 3: [ empty ]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Konversi representasi input standar LeetCode: array sisi tak berarah berbobot menjadi **Adjacency List**.

### Implementasi Python 3

```python
from collections import defaultdict
from typing import List, Tuple

def build_adjacency_list_undirected(
    num_nodes: int, 
    edges: List[List[int]]
) -> List[List[Tuple[int, int]]]:
    """
    Membangun Adjacency List berbobot menggunakan List of Lists.
    Input edges berbentuk: [u, v, weight]
    """
    # Menggunakan static array of lists untuk simpul berbasis 0 hingga num_nodes - 1
    adj: List[List[Tuple[int, int]]] = [[] for _ in range(num_nodes)]
    
    for u, v, weight in edges:
        adj[u].append((v, weight))
        adj[v].append((u, weight))  # Undirected: tambahkan kedua arah
        
    return adj

# Driver Test
if __name__ == "__main__":
    n = 4
    edge_data = [[0, 1, 5], [1, 2, 1], [2, 3, 4], [0, 3, 2]]
    graph = build_adjacency_list_undirected(n, edge_data)
    
    for node, neighbors in enumerate(graph):
        print(f"Simpul {node}: {neighbors}")
```

### Implementasi C++ (Modern C++20)

```cpp
#include <iostream>
#include <vector>

using Edge = std::pair<int, int>; // {target_node, weight}
using Graph = std::vector<std::vector<Edge>>;

Graph buildAdjacencyList(int numNodes, const std::vector<std::vector<int>>& edges) {
    Graph adj(numNodes);
    
    for (const auto& edge : edges) {
        int u = edge[0];
        int v = edge[1];
        int weight = edge[2];
        
        adj[u].emplace_back(v, weight);
        adj[v].emplace_back(u, weight); // Undirected
    }
    
    return adj;
}

int main() {
    int n = 4;
    std::vector<std::vector<int>> edges = {
        {0, 1, 5}, {1, 2, 1}, {2, 3, 4}, {0, 3, 2}
    };
    
    Graph graph = buildAdjacencyList(n, edges);
    
    for (int i = 0; i < n; ++i) {
        std::cout << "Simpul " << i << ": ";
        for (const auto& [neighbor, weight] : graph[i]) {
            std::cout << "-> (" << neighbor << ", w:" << weight << ") ";
        }
        std::cout << "\n";
    }
    return 0;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus LeetCode Klasik: Pemodelan **Implicit Grid Graph** (contoh: *LeetCode 200 - Number of Islands*). 
Sebuah matriks 2D $M \times N$ dapat dipandang sebagai graf dengan $V = M \times N$, di mana setiap sel $(r, c)$ memiliki sisi implisit ke tetangga yang valid secara ortogonal: $(r+1, c), (r-1, c), (r, c+1), (r, c-1)$.

Berikut adalah pola boiler-plate traversal matriks tanpa membuat Adjacency List eksplisit, untuk menghemat $O(M \times N)$ ruang tambahan.

```python
from typing import List

class ImplicitGridGraphTraverser:
    # Vektor offset arah (Up, Down, Left, Right)
    DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    
    @classmethod
    def get_valid_neighbors(
        cls, 
        r: int, 
        c: int, 
        rows: int, 
        cols: int, 
        grid: List[List[int]]
    ) -> List[tuple[int, int]]:
        neighbors = []
        for dr, dc in cls.DIRECTIONS:
            nr, nc = r + dr, c + dc
            # Pruning boundary check dan logical constraint (misal: bukan rintangan/air)
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                neighbors.append((nr, nc))
        return neighbors

# Kompleksitas:
# Time Complexity per cell: O(1) karena branching factor konstan (maksimal 4)
# Space Complexity: O(1) auxiliary space (mengabaikan recursive stack jika traversal dilakukan)
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Metrik / Operasi | Adjacency Matrix | Adjacency List (Vector) | Adjacency List (Hash Set) | Edge List |
| :--- | :--- | :--- | :--- | :--- |
| **Memori (Space)** | $\Theta(\|V\|^2)$ | $\Theta(\|V\| + \|E\|)$ | $\Theta(\|V\| + \|E\|)$ | $\Theta(\|E\|)$ |
| **Cek Koneksi $(u, v)$** | $O(1)$ | $O(\deg(u))$ | $O(1)$ amortized | $O(\|E\|)$ |
| **Iterasi Semua Tetangga $u$** | $\Theta(\|V\|)$ | $\Theta(\deg(u))$ | $\Theta(\deg(u))$ | $\Theta(\|E\|)$ |
| **Tambah Edge Baru** | $O(1)$ | $O(1)$ amortized | $O(1)$ amortized | $O(1)$ |
| **Hapus Edge $(u, v)$** | $O(1)$ | $O(\deg(u))$ | $O(1)$ amortized | $O(\|E\|)$ |
| **Kesesuaian Penggunaan** | Dense Graph ($\|E\| \approx \|V\|^2$), $\|V\| \le 1000$ | Sparse Graph ($\|E\| \ll \|V\|^2$), Standar LeetCode | Sering mutasi/cek keberadaan sisi | Kruskal MST, Bellman-Ford |

### Analisis Kritis: Cache Locality vs Pointer Chasing
* **Adjacency Matrix** memiliki keunggulan spatial locality yang sangat tinggi karena disimpan dalam array kontigu. CPU cache line hit rate sangat optimal saat memindai simpul baris.
* **Adjacency List** berbasis pointer (`std::list` di C++ atau linked nodes) mengalami penalti latensi memori yang parah akibat *pointer chasing* dan *cache misses*. Oleh karena itu, selalu gunakan `std::vector<std::vector<int>>` di C++ atau dynamic array flat daripada linked-list tradisional.

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Static Array Saat Label Simpul Terbatas:** Jika $V$ diketahui berurutan $0 \le u < n$, gunakan `vector<vector<int>>` atau `list[]` berukuran $n$. Hindari `unordered_map<int, vector<int>>` kecuali label node tersebar (sparse ID) atau berupa tipe non-integer (misal: string).
2. **Kapasitas Pre-alokasi:** Jika memprogram dalam C++, panggil `.reserve()` pada sub-vektor bila out-degree simpul diketahui di awal, guna meminimalisir overhead amortisasi relokasi memori.
3. **Penyimpanan State Traversal:** Pisahkan array representasi graf dari array penanda state (misal `visited: List[bool]`). Jangan pernah mengubah struktur graf secara langsung hanya untuk menandai bahwa suatu simpul telah dieksplorasi, kecuali pada graf implisit grid yang mengizinkan in-place mutation untuk menghemat memori.
4. **Validasi Indeks Node Berbasis 1 (1-Indexed Conversion):** Banyak soal LeetCode memberikan node dari interval $[1, n]$. Selalu standarisasi ke interval $[0, n-1]$ saat pembacaan input, atau inisialisasi graf dengan ukuran $n + 1$ untuk mencegah out-of-bounds bug yang subtil.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Allocating Matrix pada Large $V$ (MLE):**
   * *Kesalahan:* Menginisialisasi `matrix = [[0] * n for _ in range(n)]` saat $n = 10^5$.
   * *Dampak:* Mengalokasikan $10^{10}$ elemen; platform akan langsung mengembalikan runtime error: *Memory Limit Exceeded*.
2. **Lupa Menambahkan Arah Balik pada Undirected Graph:**
   * *Kesalahan:* Hanya melakukan `adj[u].append(v)` pada graf tak berarah.
   * *Dampak:* Traversal gagal mengeksplorasi lintasan balik, menghasilkan komponen terhubung yang terpecah palsu (*disconnected graph*).
3. **Pencarian Sisi Berulang pada Dynamic Array (TLE):**
   * *Kesalahan:* Memeriksa `if v in adj[u]` berulang kali dalam loop ketat ketika `adj[u]` adalah `list` Python biasa. Operasi ini bernilai $O(k)$ di mana $k = \deg(u)$, menyebabkan akumulasi waktu menjadi $O(V \cdot E)$.
   * *Solusi:* Konversi `adj[u]` ke tipe `set` jika logika membutuhkan frequent edge lookup.
4. **Pengabaian Multigraph / Parallel Edges:**
   * *Kesalahan:* Mengasumsikan hanya ada maksimal satu sisi antara $u$ dan $v$. Pada input LeetCode tertentu, daftar sisi dapat menduplikasi pasangan $(u, v)$ dengan bobot berbeda. Mengabaikan hal ini saat membangun adjacency matrix dapat menimpa bobot minimum dengan bobot yang lebih besar.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Soal 1: Deteksi Derajat Simpul dan Pusat Bintang
* **Problem Statement:** Diberikan graf bintang tak berarah yang memiliki $n$ simpul bernomor $1$ sampai $n$. Terdapat tepat $n - 1$ sisi sedemikian rupa sehingga satu simpul pusat terhubung ke setiap simpul lainnya. Temukan simpul pusat tersebut.
* **Input:** `edges = [[1,2],[2,3],[4,2]]`
* **Output:** `2`
* **Tantangan:** Selesaikan dalam $O(1)$ time complexity dan $O(1)$ auxiliary space complexity (LeetCode 1791 variant).

### Solusi Soal 1 (C++):
```cpp
#include <vector>

int findCenter(const std::vector<std::vector<int>>& edges) {
    // Pusat graf bintang pasti muncul di kedua edge pertama
    if (edges[0][0] == edges[1][0] || edges[0][0] == edges[1][1]) {
        return edges[0][0];
    }
    return edges[0][1];
}
```

---

### Soal 2: Konversi Representasi Bipartite Verification Check
* **Problem Statement:** Implementasikan sebuah fungsi untuk memvalidasi apakah struktur graf yang diberikan melalui Adjacency List mengandung *self-loops* atau *multigraph parallel edges*, kemudian hitung total *in-degree* dan *out-degree* untuk masing-masing simpul pada graf berarah.
* **Batasan:** $V \le 10^5$, $E \le 2 \times 10^5$. Waktu eksekusi $< 1$ detik.

### Solusi Soal 2 (Python):
```python
from typing import List, Tuple

def analyze_graph_degrees(
    num_nodes: int, 
    edges: List[List[int]]
) -> Tuple[List[int], List[int], bool]:
    """
    Mengembalikan (in_degree, out_degree, has_self_loop)
    """
    in_degree = [0] * num_nodes
    out_degree = [0] * num_nodes
    has_self_loop = False
    
    for u, v in edges:
        if u == v:
            has_self_loop = True
        out_degree[u] += 1
        in_degree[v] += 1
        
    return in_degree, out_degree, has_self_loop
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Pertanyaan 1:** Jika sebuah graf memiliki $V$ simpul dan setiap simpul memiliki tepat derajat $k$, berapakah total edge $|E|$ pada graf tersebut?
   * A. $|E| = V \times k$
   * B. $|E| = (V \times k) / 2$
   * C. $|E| = V^k$
   * D. $|E| = 2 \times (V \times k)$
2. **Pertanyaan 2:** Manakah representasi yang paling efisien dalam hal ruang (*space-efficient*) untuk memodelkan graf yang memiliki $V = 100.000$ simpul dan $E = 200.000$ sisi?
   * A. Adjacency Matrix
   * B. Incidence Matrix
   * C. Adjacency List berbasis Dynamic Array
   * D. Complete Graph Expansion
3. **Pertanyaan 3:** Berapakah kompleksitas waktu untuk mengiterasi semua tetangga dari sebuah simpul tunggal $u$ pada Adjacency Matrix berukuran $V \times V$?
   * A. $O(1)$
   * B. $O(\deg(u))$
   * C. $O(V)$
   * D. $O(V^2)$
4. **Pertanyaan 4:** Apa yang dimaksud dengan DAG (*Directed Acyclic Graph*)?
   * A. Graf tak berarah yang tidak memiliki simpul daun.
   * B. Graf berarah yang tidak memiliki sirkuit/siklus berarah sama sekali.
   * C. Graf komplit di mana setiap simpul terhubung ke semua simpul lainnya.
   * D. Graf yang dapat dipartisi menjadi dua himpunan independen.

### Kunci Jawaban
1. **B** — Berdasarkan *Handshaking Lemma*: $\sum_{v \in V} \deg(v) = 2|E| \implies V \cdot k = 2|E| \implies |E| = (V \cdot k) / 2$.
2. **C** — Adjacency List membutuhkan memori $O(V + E) \approx 3 \times 10^5$ alokasi primitif. Sebaliknya, Adjacency Matrix membutuhkan $V^2 = 10^{10}$ elemen yang memicu MLE.
3. **C** — Adjacency Matrix harus memeriksa seluruh kolom dalam satu baris secara linear berukuran $V$, terlepas dari berapa banyak simpul tetangga yang sebenarnya eksis.
4. **B** — DAG adalah graf berarah tanpa directed cycle, menjadi struktur esensial untuk dependency resolution dan topological sort.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Teks Akademik:**
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.), Bab 22: "Elementary Graph Algorithms". MIT Press.
  * Sedgewick, R., & Wayne, K. (2011). *Algorithms* (4th ed.), Bab 4: "Graphs". Addison-Wesley.
* **Dokumentasi & Standar:**
  * C++ Reference: `std::vector` contiguous storage guarantees & memory overhead (`cppreference.com`).
  * Python Documentation: Time Complexity of Internals (`wiki.python.org/moin/TimeComplexity`).
* **LeetCode Problem Set Pilihan:**
  * LeetCode 1791: *Find Center of Star Graph* (Direct topology analysis)
  * LeetCode 997: *Find the Town Judge* (In-degree & Out-degree modeling)
  * LeetCode 133: *Clone Graph* (Explicit graph copying & mapping)
  * LeetCode 200: *Number of Islands* (Implicit grid representation)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Graf $G = (V, E)$ adalah abstraksi relasional sentral dalam ilmu komputer yang mengklasifikasikan relasi antar entitas menjadi terarah (*directed*), tak berarah (*undirected*), berbobot (*weighted*), atau tanpa bobot (*unweighted*).
2. **Adjacency Matrix** memiliki kompleksitas ruang kuadratik $\Theta(V^2)$ dan konstan $O(1)$ untuk edge lookup. Struktur ini hanya direkomendasikan untuk graf padat (*dense graphs*) atau saat batasan node kecil ($V \le 1000$).
3. **Adjacency List** adalah representasi default pada competitive programming dengan kompleksitas ruang optimal $\Theta(V + E)$ dan pemindaian tetangga $O(\deg(u))$.
4. Masalah berbasis grid dua dimensi pada LeetCode tidak memerlukan instansiasi graf eksplisit; relasi sisi ditangani secara implisit menggunakan array pergeseran koordinat (*coordinate directional vectors*).

---

## SEKSI 17 — GLOSARIUM

* **Adjacency List:** Struktur data di mana setiap simpul mengelola daftar (list/vector) yang berisi simpul-simpul target yang terhubung langsung dengannya.
* **Adjacency Matrix:** Matriks dua dimensi berukuran $V \times V$ yang menandai ada tidaknya serta bobot sisi antara simpul baris ke simpul kolom.
* **Branching Factor:** Rata-rata jumlah simpul cabang penerus atau tetangga yang dapat dieksplorasi dari sebuah simpul.
* **Dense Graph:** Graf di mana jumlah sisi mendekati jumlah sisi maksimum teoritis ($|E| \approx |V|^2$).
* **Handshaking Lemma:** Teorema dasar teori graf yang menyatakan bahwa jumlah seluruh derajat simpul pada graf tak berarah adalah tepat dua kali jumlah sisi graf tersebut.
* **Implicit Graph:** Representasi graf di mana sisi dan simpul tidak dialokasikan di dalam memori sebagai struktur data eksplisit, melainkan dievaluasi secara dinamis melalui aturan transisi logis (misalnya kisi koordinat $2\text{D}$).
* **Sparse Graph:** Graf di mana jumlah sisi jauh lebih kecil daripada kapasitas kuadratik maksimumnya ($|E| \ll |V|^2$).

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedagogy Tip:** Saat peserta didik pertama kali mempelajari graf, mereka cenderung ingin membuat custom class `Node` dengan pointer referensi (`class Node { int val; vector<Node*> neighbors; }`). Tekankan bahwa dalam batasan waktu wawancara teknis dan LeetCode, alokasi objek kecil yang berulang secara masif memicu overhead *garbage collection* (Java/Python) atau fragmentasi memori heap (C++). Ajarkan mereka untuk selalu mengutamakan representasi flat array of vectors berbasis indeks integer primitif.
* **Common Bottleneck:** Mahasiswa sering bingung membedakan antara graf statis terputus (*disconnected graph*) dan pohon (*tree*). Tekankan relasi fundamental: Suatu graf tak berarah dengan $V$ simpul adalah pohon jika dan hanya jika ia terhubung (*connected*) dan memiliki tepat $V - 1$ sisi.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal Rilis:** 2025-05-18
* **Catatan Perubahan:**
  * Inisialisasi materi fondasi teori graf dan topologi representasi data.
  * Penambahan implementasi komparatif multi-bahasa (Python 3 & Modern C++20).
  * Penambahan bab analisis memori tingkat rendah (*cache locality*) dan *Handshaking Lemma*.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `01-Core-Foundations/Bab 06 - Heaps & Priority Queues/Module 02 - Advanced Heap Operations & Median Maintenance`
* **Modul Berikutnya:** `01-Core-Foundations/Bab 07 - Graph Theory & Network Topologies/Module 02 - Breadth-First Search (BFS) & Shortest Path in Unweighted Graphs`
* **Daftar Modul Bab 07:**
  * Modul 01: Fundamental Graph Representations & Topologies *(Modul Saat Ini)*
  * Modul 02: Breadth-First Search (BFS) & Shortest Path in Unweighted Graphs
  * Modul 03: Depth-First Search (DFS), Cycle Detection & Connectivity
  * Modul 04: Topological Sorting & Directed Acyclic Graphs (DAG)
  * Modul 05: Disjoint Set Union (DSU / Union-Find) & Dynamic Connectivity