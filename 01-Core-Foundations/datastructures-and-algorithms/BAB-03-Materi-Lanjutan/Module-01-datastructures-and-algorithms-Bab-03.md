# Kurikulum: Data Structures & Algorithms
## Kategori: 01-Core-Foundations
### Bab 03: Pohon & Struktur Hierarkis

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `DSA-01-03-01`
* **Judul Modul**: Fundamental Pohon: Terminologi, Representasi Memori, dan Binary Search Tree (BST)
* **Tingkat Kesulitan**: Intermediate
* **Estimasi Waktu Penyelesaian**: 180 Menit
* **Prasyarat Pengetahuan**:
  * Pointer dan Alokasi Memori Dinamis (Heap vs. Stack)
  * Rekursi dan Analisis Call Stack
  * Struktur Data Linier (Linked List, Array)
  * Notasi Asimptotik Big-O (Time & Space Complexity)
* **Kaitan dengan Modul Lain**:
  * *Prasyarat*: `DSA-01-02-02` (Singly & Doubly Linked Lists), `DSA-01-01-03` (Analisis Kompleksitas Algoritma)
  * *Lanjutan Langsung*: `DSA-01-03-02` (Self-Balancing BST: AVL & Red-Black Trees), `DSA-01-03-03` (B-Trees & LSM-Trees untuk Penyimpanan Sekunder)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Memetakan Topologi Pohon**: Mengidentifikasi secara matematis relasi antar node (*root*, *internal node*, *leaf*, *ancestor*, *descendant*), serta menghitung metrik struktural (*depth*, *height*, *degree*, *balance factor*) dengan akurasi 100%.
2. **Merancang Representasi Memori**: Memilih dan mengimplementasikan representasi struktur data pohon yang optimal (pointer-based linked nodes vs. implicit array representation) berdasarkan karakteristik beban kerja dan fragmentasi memori.
3. **Mengimplementasikan Operasi Primitif BST**: Menulis kode invarian BST tanpa cacat logika untuk operasi pencarian (*search*), penambahan (*insertion*), dan penghapusan node (*deletion* menggunakan substitusi Hibbard / predecessor/successor).
4. **Mengeksekusi Algoritma Traversal**: Mengimplementasikan algoritma traversal *depth-first* (pre-order, in-order, post-order) baik secara rekursif maupun iteratif menggunakan *explicit stack*, serta *breadth-first traversal* (level-order) menggunakan *queue*.
5. **Mengevaluasi Degradasi Performa**: Mengukur dan membuktikan kondisi degenerasi BST ke linked list ($O(N)$) versus kondisi ideal balanced ($O(\log N)$) serta implikasinya terhadap *cache locality*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
Hierarchical Data Models
         │
         ├── Definisi Formal Graf Asiklik Terhubung (Directed Acyclic Graph / Tree)
         │       ├── Root, Edge, Parent, Child, Sibling, Subtree
         │       └── Metrik: Height = max(edges to leaf), Depth = edges from root
         │
         ├── Taksonomi Binary Tree
         │       ├── Full Binary Tree (0 atau 2 children per node)
         │       ├── Complete Binary Tree (semua level penuh kecuali level terakhir, rata kiri)
         │       ├── Perfect Binary Tree (semua internal node punya 2 children, leaf di level sama)
         │       └── Degenerate/Pathological Tree (ekuivalen dengan Linked List)
         │
         ├── Representasi Memori
         │       ├── Node-Based (Pointer/Reference): struct { T value; Node* left; Node* right; }
         │       └── Implicit Array-Based: Indeks $i \rightarrow$ Left: $2i+1$, Right: $2i+2$, Parent: $\lfloor(i-1)/2\rfloor$
         │
         ├── Binary Search Tree (BST) Invariant
         │       └── $\forall x \in \text{LeftSubtree}(u), \text{key}(x) < \text{key}(u) \quad \land \quad \forall y \in \text{RightSubtree}(u), \text{key}(y) > \text{key}(u)$
         │
         └── Operasi Inti & Traversal
                 ├── Search & Insert ($O(h)$ di mana $h = \text{height}$)
                 ├── Hibbard Deletion (Kasus: 0 child, 1 child, 2 children)
                 ├── Depth-First Search (DFS): Pre-order, In-order (Sorted output), Post-order
                 └── Breadth-First Search (BFS): Level-order Traversal
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Pelanggaran Batasan Struktur Linier**:
   Struktur data linier membatasi operasi pencarian dan modifikasi. Array terurut menawarkan pencarian $O(\log N)$ via Binary Search, tetapi penambahan/penghapusan elemen membutuhkan *memory shifting* sebesar $O(N)$. Linked List memungkinkan modifikasi pointer $O(1)$ pada node yang diketahui, tetapi akses pencariannya selalu $O(N)$. Pohon, khususnya BST, menjembatani keterbatasan ini dengan menawarkan pencarian, penambahan, dan penghapusan dalam kompleksitas waktu $O(\log N)$ pada kondisi seimbang.

2. **Fondasi Abstraksi Tingkat Tinggi**:
   Hampir seluruh sistem rekayasa perangkat lunak modern bergantung pada variasi pohon:
   * **Database Engine**: Indexing relasional B+ Tree (MySQL InnoDB, PostgreSQL) dan LSM-Tree (Cassandra, RocksDB).
   * **Compiler & Interpreter**: Abstract Syntax Tree (AST) untuk parsing, semantic analysis, dan bytecode generation.
   * **Sistem Berkas (Filesystem)**: Struktur direktori UNIX/NTFS (*inode hierarchy*).
   * **Networking & Routing**: Radix Tree dan Trie untuk perutean tabel IP (CIDR lookup).
   * **Domain Specific Frameworks**: DOM (Document Object Model) pada web browser dan rendering tree pada GUI engine.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Definisi Matematis
Secara formal, **Tree** adalah graf asiklik tak berarah terhubung $G = (V, E)$, di mana $|E| = |V| - 1$. Dalam rekayasa perangkat lunak, kita hampir selalu merujuk pada **Rooted Directed Tree**, yaitu struktur hierarkis dengan tepat satu simpul akar (*root*) yang tidak memiliki *parent*, dan setiap simpul lainnya memiliki tepat satu *parent*.

### 2. Aksioma & Metrik Kunci
* **Root**: Node teratas tanpa edge masuk (*in-degree* = 0).
* **Leaf (Terminal Node)**: Node tanpa edge keluar (*out-degree* = 0).
* **Internal Node**: Node non-leaf yang memiliki minimal satu *child*.
* **Path**: Urutan node $v_1, v_2, \dots, v_k$ sedemikian rupa sehingga terdapat edge dari $v_i$ ke $v_{i+1}$.
* **Depth (Kedalaman)**: Jumlah edge dari root ke node tertentu. Depth dari root adalah $0$.
* **Height (Tinggi) Node**: Jumlah edge pada path terpanjang dari node tersebut ke leaf. Height dari leaf adalah $0$.
* **Height Tree**: Height dari root node. Pohon dengan 1 node memiliki height $0$. (Beberapa literatur mendefinisikan tinggi pohon kosong sebagai $-1$).
* **Level**: Sekumpulan node dengan kedalaman yang identik ($Level = Depth$).

### 3. Klasifikasi Binary Tree
Binary tree adalah pohon di mana setiap simpul memiliki paling banyak dua anak, yang secara konseptual dibedakan menjadi *left child* dan *right child*.

| Tipe Binary Tree | Definisi Formal | Karakteristik Jumlah Node ($N$) terhadap Height ($h$) |
| :--- | :--- | :--- |
| **Full** | Setiap node memiliki 0 atau 2 children. Tidak boleh ada node beranak tunggal. | $2h + 1 \le N \le 2^{h+1} - 1$ |
| **Complete** | Semua level terisi penuh kecuali level terakhir, dan level terakhir terisi dari kiri ke kanan tanpa celah (*gap*). | $2^h \le N \le 2^{h+1} - 1$ |
| **Perfect** | Semua internal node memiliki 2 children, dan semua leaf berada pada level yang sama. | $N = 2^{h+1} - 1$ |
| **Degenerate** | Setiap internal node hanya memiliki tepat satu child. Memiliki topologi linier. | $N = h + 1$ |

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Representasi Memori: Pointer vs. Implicit Array

#### A. Node-Based (Linked Allocation)
Setiap node dialokasikan secara independen pada heap memori.
* **Layout Memori**: Node terdiri dari payload data dan dua pointer (`left` dan `right`).
* **Kelebihan**: Fleksibel, alokasi dinamis tanpa overhead pemindahan memori skala besar saat pohon bertumbuh.
* **Kekurangan**: Overhead pointer (16 byte pada sistem 64-bit hanya untuk 2 pointer per node). Pola akses traversal melompat-lompat di heap, menyebabkan *cache miss* yang signifikan (buruknya *spatial locality*).

#### B. Implicit Array-Based Representation
Biasanya digunakan untuk Complete Binary Tree (misalnya Binary Heap).
* **Aturan Indeks (0-indexed)**:
  * Node pada indeks $i$:
    * Parent: $\lfloor \frac{i - 1}{2} \rfloor$
    * Left Child: $2i + 1$
    * Right Child: $2i + 2$
* **Kelebihan**: Memory density 100% tanpa pointer overhead; *cache-friendly* karena pembacaan sequential array.
* **Kekurangan**: Pemborosan memori parah jika pohon tidak seimbang atau sparse (contoh: pohon degenerat dengan depth $k$ membutuhkan array berukuran $2^{k+1}-1$ meskipun hanya ada $k+1$ node).

### 2. Invarian Binary Search Tree (BST)
BST adalah Binary Tree dengan properti terurut:
Untuk setiap node $P$:
* Semua nilai pada sub-pohon kiri $P$ harus **lebih kecil secara strictly** daripada nilai $P$.
* Semua nilai pada sub-pohon kanan $P$ harus **lebih besar secara strictly** daripada nilai $P$.
* Tidak diperbolehkan adanya duplikasi kunci (dalam implementasi standar murni; jika duplikasi diizinkan, kontrak harus menetapkan apakah masuk ke kiri ($\le$) atau kanan ($\ge$)).

### 3. Mekanisme Algoritma Penghapusan (Hibbard Deletion)
Operasi penghapusan pada BST adalah algoritma yang paling rentan terhadap kesalahan edge-case karena harus mempertahankan invarian BST tanpa merusak kontinuitas struktur:

1. **Kasus 1: Leaf Node (0 Child)**:
   * Langsung putuskan pointer dari parent ke node ini, lalu dealokasikan memori node target.
2. **Kasus 2: Single Child (1 Child)**:
   * Pointer dari parent yang mengarah ke target diarahkan langsung (*bypass*) ke child tunggal milik target.
3. **Kasus 3: Two Children (2 Children)**:
   * Cari simpul pengganti:
     * **In-order Successor**: Node terkecil di sub-pohon kanan (jalan sekali ke kanan, lalu ke kiri terus hingga mentok), ATAU
     * **In-order Predecessor**: Node terbesar di sub-pohon kiri.
   * Salin nilai successor ke node target.
   * Hapus successor dari sub-pohon kanan (karena successor dijamin memiliki maksimal 1 child, yaitu right child, penghapusan ini tereduksi ke Kasus 1 atau Kasus 2).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Struktur Topologi & Metrik

```text
               Level 0 (Depth=0)        [ 50 ]  <-- Root (Height=3)
                                      /        \
               Level 1 (Depth=1)   [ 30 ]       [ 70 ]
                                  /      \     /      \
               Level 2 (Depth=2) [ 20 ]  [ 40 ] [ 60 ]  [ 80 ]
                                 /
               Level 3 (Depth=3) [ 10 ] <-- Leaf (Height=0)
```

### 2. Layout Memori Internal: Node Pointer di Virtual Address Space

```text
Heap Address Space:
-------------------------------------------------------------------------
Alamat:    0x1000             0x1040             0x1080
Konten:    Node (50)          Node (30)          Node (70)
Data:      val: 50            val: 30            val: 70
Pointers:  left:  0x1040      left:  0x10A0      left:  nullptr
           right: 0x1080      right: 0x10C0      right: nullptr
-------------------------------------------------------------------------
```

### 3. Alur Penghapusan Kasus 2 Children (Hibbard Deletion)

Menghapus Node `50` dari BST:

```text
Langkah 1: Identifikasi Node Target & Successor
              [ 50 ] <--- Target (Akan dihapus)
            /        \
         [ 30 ]      [ 70 ]
                   /        \
 (Successor) -> [ 60 ]      [ 80 ]
                    \
                    [ 65 ]

Langkah 2: Copy Value Successor ke Target
              [ 60 ] <--- Nilai digantikan oleh 60
            /        \
         [ 30 ]      [ 70 ]
                   /        \
                [ 60 ]      [ 80 ]
                    \
                    [ 65 ]

Langkah 3: Hapus Node Successor Asli (Bypass ke Right Child-nya: 65)
              [ 60 ]
            /        \
         [ 30 ]      [ 70 ]
                   /        \
                [ 65 ]      [ 80 ]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi Binary Search Tree fundamental dalam bahasa C++ standar industri, mencakup Insert, Search, dan In-order Traversal.

```cpp
#include <iostream>
#include <memory>

struct BSTNode {
    int key;
    std::unique_ptr<BSTNode> left;
    std::unique_ptr<BSTNode> right;

    explicit BSTNode(int val) : key(val), left(nullptr), right(nullptr) {}
};

class SimpleBST {
private:
    std::unique_ptr<BSTNode> root;

    bool insertInternal(std::unique_ptr<BSTNode>& node, int val) {
        if (!node) {
            node = std::make_unique<BSTNode>(val);
            return true;
        }
        if (val < node->key) {
            return insertInternal(node->left, val);
        } else if (val > node->key) {
            return insertInternal(node->right, val);
        }
        return false; // Nilai duplikat tidak diizinkan
    }

    bool searchInternal(const std::unique_ptr<BSTNode>& node, int val) const {
        if (!node) return false;
        if (val == node->key) return true;
        if (val < node->key) return searchInternal(node->left, val);
        return searchInternal(node->right, val);
    }

    void inorderInternal(const std::unique_ptr<BSTNode>& node) const {
        if (!node) return;
        inorderInternal(node->left);
        std::cout << node->key << " ";
        inorderInternal(node->right);
    }

public:
    SimpleBST() : root(nullptr) {}

    bool insert(int val) {
        return insertInternal(root, val);
    }

    bool search(int val) const {
        return searchInternal(root, val);
    }

    void printInOrder() const {
        inorderInternal(root);
        std::cout << "\n";
    }
};

int main() {
    SimpleBST bst;
    bst.insert(50);
    bst.insert(30);
    bst.insert(70);
    bst.insert(20);
    bst.insert(40);

    std::cout << "Inorder Traversal: ";
    bst.printInOrder(); // Output: 20 30 40 50 70

    std::cout << "Search 40: " << (bst.search(40) ? "Ditemukan" : "Tidak Ada") << "\n";
    std::cout << "Search 99: " << (bst.search(99) ? "Ditemukan" : "Tidak Ada") << "\n";

    return 0;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi tingkat produksi: In-Memory Symbol Table / Key-Value Store dengan penanganan Hibbard Deletion, iteratif stack traversal, dan level-order traversal.

```cpp
#include <iostream>
#include <string>
#include <vector>
#include <queue>
#include <stack>
#include <optional>
#include <cassert>

template <typename K, typename V>
class BinarySearchTree {
private:
    struct Node {
        K key;
        V value;
        Node* left;
        Node* right;

        Node(K k, V v) : key(k), value(v), left(nullptr), right(nullptr) {}
    };

    Node* root = nullptr;
    size_t node_count = 0;

    Node* insertInternal(Node* current, K key, V value, bool& inserted) {
        if (!current) {
            inserted = true;
            return new Node(key, value);
        }
        if (key < current->key) {
            current->left = insertInternal(current->left, key, value, inserted);
        } else if (key > current->key) {
            current->right = insertInternal(current->right, key, value, inserted);
        } else {
            current->value = value; // Update value jika kunci sudah ada
            inserted = false;
        }
        return current;
    }

    Node* findMin(Node* node) const {
        while (node && node->left != nullptr) {
            node = node->left;
        }
        return node;
    }

    Node* removeInternal(Node* current, const K& key, bool& removed) {
        if (!current) {
            removed = false;
            return nullptr;
        }

        if (key < current->key) {
            current->left = removeInternal(current->left, key, removed);
        } else if (key > current->key) {
            current->right = removeInternal(current->right, key, removed);
        } else {
            removed = true;
            // Kasus 1 & 2: Tanpa child atau satu child
            if (!current->left) {
                Node* temp = current->right;
                delete current;
                return temp;
            } else if (!current->right) {
                Node* temp = current->left;
                delete current;
                return temp;
            }

            // Kasus 3: Memiliki dua child
            Node* successor = findMin(current->right);
            current->key = successor->key;
            current->value = successor->value;
            // Hapus successor dari sub-pohon kanan
            current->right = removeInternal(current->right, successor->key, removed);
        }
        return current;
    }

    void destroyRecursive(Node* node) {
        if (!node) return;
        destroyRecursive(node->left);
        destroyRecursive(node->right);
        delete node;
    }

public:
    BinarySearchTree() = default;
    ~BinarySearchTree() {
        destroyRecursive(root);
    }

    // Hindari shallow copy implisit demi keselamatan memori
    BinarySearchTree(const BinarySearchTree&) = delete;
    BinarySearchTree& operator=(const BinarySearchTree&) = delete;

    size_t size() const { return node_count; }
    bool empty() const { return node_count == 0; }

    void put(K key, V value) {
        bool inserted = false;
        root = insertInternal(root, key, value, inserted);
        if (inserted) ++node_count;
    }

    std::optional<V> get(const K& key) const {
        Node* curr = root;
        while (curr) {
            if (key < curr->key) {
                curr = curr->left;
            } else if (key > curr->key) {
                curr = curr->right;
            } else {
                return curr->value;
            }
        }
        return std::nullopt;
    }

    bool remove(const K& key) {
        bool removed = false;
        root = removeInternal(root, key, removed);
        if (removed) --node_count;
        return removed;
    }

    // Non-recursive (Iterative) In-Order Traversal menggunakan Explicit Stack
    std::vector<std::pair<K, V>> getInOrderIterative() const {
        std::vector<std::pair<K, V>> result;
        std::stack<Node*> st;
        Node* curr = root;

        while (curr != nullptr || !st.empty()) {
            while (curr != nullptr) {
                st.push(curr);
                curr = curr->left;
            }
            curr = st.top();
            st.pop();
            result.emplace_back(curr->key, curr->value);
            curr = curr->right;
        }
        return result;
    }

    // Breadth-First / Level-Order Traversal
    std::vector<std::vector<K>> getLevelOrder() const {
        std::vector<std::vector<K>> result;
        if (!root) return result;

        std::queue<Node*> q;
        q.push(root);

        while (!q.empty()) {
            size_t level_size = q.size();
            std::vector<K> current_level;
            current_level.reserve(level_size);

            for (size_t i = 0; i < level_size; ++i) {
                Node* node = q.front();
                q.pop();
                current_level.push_back(node->key);

                if (node->left) q.push(node->left);
                if (node->right) q.push(node->right);
            }
            result.push_back(std::move(current_level));
        }
        return result;
    }
};

int main() {
    BinarySearchTree<std::string, int> symbolTable;

    // Masukkan data transaksi user
    symbolTable.put("charlie", 100);
    symbolTable.put("alice", 50);
    symbolTable.put("bob", 75);
    symbolTable.put("david", 200);
    symbolTable.put("eve", 150);

    assert(symbolTable.size() == 5);
    std::cout << "Data bob: " << symbolTable.get("bob").value_or(-1) << "\n";

    // Modifikasi eksisting
    symbolTable.put("bob", 90);
    assert(symbolTable.get("bob").value() == 90);

    // Traversal In-Order
    std::cout << "\nIn-Order Key-Value:\n";
    for (const auto& [k, v] : symbolTable.getInOrderIterative()) {
        std::cout << "  " << k << " : " << v << "\n";
    }

    // Traversal Level-Order
    std::cout << "\nLevel-Order Hierarchy:\n";
    auto levels = symbolTable.getLevelOrder();
    for (size_t i = 0; i < levels.size(); ++i) {
        std::cout << "  Level " << i << ": ";
        for (const auto& k : levels[i]) std::cout << k << " ";
        std::cout << "\n";
    }

    // Penghapusan Node 2 Children (charlie adalah root)
    std::cout << "\nMenghapus 'charlie'...\n";
    symbolTable.remove("charlie");
    assert(symbolTable.size() == 4);
    assert(!symbolTable.get("charlie").has_value());

    std::cout << "In-Order Pasca Penghapusan:\n";
    for (const auto& [k, v] : symbolTable.getInOrderIterative()) {
        std::cout << "  " << k << " : " << v << "\n";
    }

    return 0;
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Struktur Data | Search (Avg) | Search (Worst) | Insert (Avg) | Insert (Worst) | Delete (Worst) | Space Overhead | Cache Locality |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Sorted Array** | $O(\log N)$ | $O(\log N)$ | $O(N)$ | $O(N)$ | $O(N)$ | Rendah (0 byte ptr) | Sangat Tinggi |
| **Doubly Linked List**| $O(N)$ | $O(N)$ | $O(1)^*$ | $O(1)^*$ | $O(1)^*$ | 2 pointer/node | Sangat Rendah |
| **Unbalanced BST** | $O(\log N)$ | $O(N)$ | $O(\log N)$ | $O(N)$ | $O(N)$ | 2 pointer/node | Sangat Rendah |
| **Balanced BST (AVL)**| $O(\log N)$ | $O(\log N)$ | $O(\log N)$ | $O(\log N)$ | $O(\log N)$ | 2 ptr + 1 byte h | Sangat Rendah |
| **Hash Table** | $O(1)$ | $O(N)$ | $O(1)$ | $O(N)$ | $O(N)$ | Tinggi (Load factor) | Moderat |

*\*Dengan asumsi pointer iterator ke node sudah diketahui.*

### Implikasi Cache & Virtual Memory
Unbalanced BST mengandalkan dynamic memory allocation di heap (`malloc`/`new`). Setiap alokasi node dapat menghasilkan segmen memori yang terpencar di alamat non-kontigu. Akibatnya:
* **CPU Cache Trashing**: Traversal dari root ke leaf menyebabkan serial *pointer chasing*. Setiap dereferensi berisiko mengalami *L1/L2 data cache miss*.
* **Memory Bloat**: Menyimpan payload 4-byte (integer) pada arsitektur 64-bit membutuhkan 16 byte untuk dua buah pointer (left/right) ditambah padding alignment alokator (biasanya 8 byte), sehingga total konsumsi adalah 24-32 byte per node (efisiensi ruang < 20%).

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Iterative Traversal untuk Produksi**: Rekursi pada BST yang tidak seimbang dapat menyebabkan pemanggilan stack frame sedalam $O(N)$. Pada input berukuran $N = 10^5$, ini dapat memicu **Stack Overflow** (panjang stack C/C++ default terbatas 1MB-8MB). Ubah ke iteratif dengan explicit stack berbasis heap jika pohon tidak dijamin seimbang.
2. **RAII & Memory Ownership**: Hindari *raw pointers* untuk manajemen siklus hidup node jika memungkinkan. Gunakan `std::unique_ptr` untuk mengekspresikan kepemilikan pohon tunggal (kecuali jika struktur data memerlukan threading/parent pointer di mana raw-pointer non-owning lebih tepat).
3. **Optimalkan Hibbard Deletion**: Hibbard deletion konvensional (selalu memilih successor kanan) menyebabkan pohon mengalami asimetri struktural seiring waktu (pohon cenderung miring ke kiri setelah ribuan operasi insert-delete acak). Lakukan alternasi acak antara mengambil *predecessor* dari kiri atau *successor* dari kanan.
4. **Pass-by-Reference pada Pointer Root**: Saat memodifikasi child via rekursi, gunakan `Node*&` (pointer reference) atau kembalikan pointer node yang diperbarui untuk mencegah *pointer dangling* atau mutasi cabang yang salah.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Stack Overflow akibat Degenerasi Input Terurut
```cpp
// ANTI-PATTERN: Memasukkan array terurut langsung ke BST polos
BinarySearchTree<int, int> bst;
for (int i = 1; i <= 100000; ++i) {
    bst.put(i, i); // Menghasilkan struktur degenerate/linked list miring ke kanan!
}
// Eksekusi fungsi rekursif apa pun di sini akan menyebabkan Segfault / Stack Overflow.
```
*Solusi*: Jika input terurut, buat seimbang menggunakan divide-and-conquer (mirip binary search) atau gunakan Self-Balancing BST.

### 2. Validasi BST yang Cacat (Local vs. Global Invariant)
Banyak developer membuat fungsi validasi BST yang salah hanya dengan mengecek kondisi lokal node terhadap anaknya:
```cpp
// SALAH BESAR: Hanya mengecek left < current < right secara lokal
bool isBSTBroken(Node* node) {
    if (!node) return true;
    if (node->left && node->left->val >= node->val) return false;
    if (node->right && node->right->val <= node->val) return false;
    return isBSTBroken(node->left) && isBSTBroken(node->right);
}
// Struktur ini lolos validasi rusak di atas, padahal BUKAN BST:
//       20
//      /  \
//    10    30
//         /
//        5  <-- SALAH! 5 berada di sub-pohon kanan 20, melanggar invarian global (5 < 20)!
```
*Koreksi*: Validasi harus menyertakan rentang min-max global yang diizinkan untuk setiap sub-pohon:
```cpp
bool isValidBST(Node* node, long minVal, long maxVal) {
    if (!node) return true;
    if (node->val <= minVal || node->val >= maxVal) return false;
    return isValidBST(node->left, minVal, node->val) &&
           isValidBST(node->right, node->val, maxVal);
}
```

### 3. Memory Leak Saat Menghapus Node
Melakukan *overwrite* pointer referensi tanpa melakukan `delete` pada alokasi node asli akan menghasilkan *orphan node* yang menetap di heap memori.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Validasi BST Global (Tingkat: Easy)
Implementasikan fungsi `bool isValidBST(Node* root)` yang mengevaluasi apakah sebuah Binary Tree mematuhi invarian BST secara menyeluruh dalam $O(N)$ waktu dan $O(h)$ memori tambahan.

### Latihan 2: Lowest Common Ancestor (LCA) pada BST (Tingkat: Medium)
Diberikan sebuah BST dan dua node $p$ dan $q$. Temukan Lowest Common Ancestor dari kedua node tersebut dengan memanfaatkan properti nilai kunci BST (tanpa menyimpan path dan tanpa melakukan full tree scan). Waktu: $O(h)$.

### Latihan 3: Konversi BST ke Doubly Linked List Terurut di Tempat (Tingkat: Hard)
Ubahlah sebuah BST menjadi sorted circular doubly-linked list secara *in-place* (tanpa mengalokasikan node baru). Pointer `left` harus berfungsi sebagai pointer `prev`, dan pointer `right` harus berfungsi sebagai pointer `next`.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Berapa jumlah maksimum node pada Binary Tree dengan tinggi $h$ (di mana tinggi root adalah 0)?**
   * A) $2^h$
   * B) $2^h - 1$
   * C) $2^{h+1} - 1$
   * D) $2h + 1$
   * *Jawaban*: C. Deret geometri $\sum_{i=0}^h 2^i = 2^{h+1} - 1$.

2. **Diberikan urutan in-order traversal: `[D, B, E, A, F, C]` dan pre-order traversal: `[A, B, D, E, C, F]`. Apa root dari sub-pohon kanan node `A`?**
   * A) B
   * B) C
   * C) E
   * D) F
   * *Jawaban*: B. Dari pre-order, `A` adalah root. Pada in-order, elemen di kanan `A` adalah `[F, C]`. Pada pre-order, urutan setelah sub-pohon kiri (`B, D, E`) adalah `C, F`, sehingga `C` adalah root dari sub-pohon kanan.

3. **Mengapa in-order traversal pada BST selalu menghasilkan urutan elemen yang terurut menaik (sorted)?**
   * A) Karena algoritma mengunjungi leaf terlebih dahulu.
   * B) Karena invarian BST mendefinisikan Left < Current < Right, yang berkorespondensi presisi dengan urutan pemrosesan in-order: proses seluruh sub-pohon kiri, lalu proses current node, lalu proses sub-pohon kanan.
   * C) Karena stack secara implisit menyortir data saat pop.
   * D) Karena memori dialokasikan secara sequential.
   * *Jawaban*: B.

4. **Operasi Hibbard Deletion pada node dengan 2 children memiliki kompleksitas asimptotik terburuk sebesar:**
   * A) $O(1)$
   * B) $O(h)$ di mana $h$ adalah tinggi pohon
   * C) $O(N \log N)$
   * D) $O(N^2)$
   * *Jawaban*: B. Mencari in-order successor membutuhkan waktu proporsional terhadap tinggi sub-pohon kanan $O(h)$, dan penghapusan fisik successor adalah $O(h)$.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C.** (2022). *Introduction to Algorithms* (4th ed.). MIT Press. — **Chapter 12: Binary Search Trees**.
* **Sedgewick, R., & Wayne, K.** (2011). *Algorithms* (4th ed.). Addison-Wesley Professional. — **Section 3.2: Binary Search Trees**.
* **Knuth, D. E.** (1997). *The Art of Computer Programming, Volume 3: Sorting and Searching* (2nd ed.). Addison-Wesley. — **Section 6.2.2: Binary Tree Searching**.
* **Linux Kernel Source Tree**: Implementasi struktur data intrusive tree (`include/linux/rbtree.h`).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Pohon adalah struktur data non-linier hierarkis yang merepresentasikan relasi bertingkat tanpa siklus.
2. Binary Search Tree (BST) memberlakukan relasi urutan strictly: semua kunci di sub-pohon kiri lebih kecil dari root, dan semua kunci di sub-pohon kanan lebih besar dari root.
3. Kinerja operasi dasar (Search, Insert, Delete) pada BST bergantung penuh pada nilai tinggi pohon ($h$). Pada kondisi terbaik/rata-rata $h = O(\log N)$, namun pada kondisi input terurut dapat mengalami degenerasi menjadi linked list dengan $h = O(N)$.
4. Penghapusan node dengan dua children dapat ditangani menggunakan **Hibbard Deletion**, yaitu mengganti nilai node target dengan nilai in-order successor (atau predecessor), kemudian menghapus successor aslinya yang memiliki paling banyak 1 child.
5. Traversal depth-first traversal (Pre, In, Post) mengeksplorasi cabang ke bawah terlebih dahulu, sedangkan Breadth-First (Level-Order) mengeksplorasi simpul lapis demi lapis menggunakan queue. Traversal In-Order pada BST selalu memproduksi data yang terurut menaik.

---

## SEKSI 17 — GLOSARIUM

* **In-order Successor**: Node dengan nilai kunci terkecil yang lebih besar daripada node acuan (terletak pada node terkiri dari sub-pohon kanan).
* **In-order Predecessor**: Node dengan nilai kunci terbesar yang lebih kecil daripada node acuan (terletak pada node terkanan dari sub-pohon kiri).
* **Degenerate Tree**: Kondisi di mana setiap node internal hanya memiliki satu child, mengubah topologi pohon menjadi ekuivalen struktural dengan singly-linked list.
* **Spatial Locality**: Karakteristik eksekusi program di mana alamat memori yang berdekatan dengan alamat yang baru saja diakses cenderung akan diakses kembali dalam waktu dekat.
* **Pointer Chasing**: Pola eksekusi CPU di mana data berikutnya baru bisa dibaca setelah dereferensi pointer saat ini, membatasi kemampuan hardware prefetcher dan sering memicu CPU stall akibat cache miss.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi**:
  Pastikan peserta didik tidak menghafal definisi tanpa memahami implikasi memorinya. Berikan latihan visual tracing di papan tulis saat menjelaskan proses rotasi dan penghapusan kasus dua anak. Tunjukkan profil konsumsi heap memori melalui debugger/Valgrind untuk membuktikan fragmentasi memori akibat pointer-based node tree.
* **Analogi Pengajaran**:
  Gunakan analogi silsilah keluarga atau sistem bagan turnamen olahraga untuk menjelaskan konsep relasi parent-child, root, dan path. Untuk BST, gunakan analogi permainan tebak angka "Lebih Tinggi / Lebih Rendah" untuk memvisualisasikan binary partitioning.
* **Fokus Penilaian Hands-on**:
  Periksa implementasi deletion mahasiswa secara ketat: pastikan tidak terjadi kebocoran memori (memory leak) dan tidak ada dangling pointer ketika successor dipindahkan.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2026)**:
  * Rilis perdana modul fundamental pohon sesuai spesifikasi format 20 seksi GEMINI.md.
  * Penambahan implementasi produksi C++ Key-Value Symbol Table.
  * Analisis cache locality dan perbandingan layout memori virtual.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `DSA-01-02-04` — Hash Tables & Collision Resolution Strategies
* **Modul Berikutnya**: `DSA-01-03-02` — Self-Balancing Trees: AVL Trees & Red-Black Trees Balancing Mechanisms
* **Repositori Kurikulum**: `core-foundations/datastructures-and-algorithms/chapter-03`