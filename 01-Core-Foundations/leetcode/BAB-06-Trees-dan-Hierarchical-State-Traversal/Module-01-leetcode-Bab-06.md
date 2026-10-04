# MODUL 06-01: TREES & HIERARCHICAL STATE TRAVERSAL

---

## SEKSI 01 — IDENTITAS MODUL

*   **Track:** Technical Interview Preparation & Algorithmic Engineering
*   **Course:** 01-Core-Foundations
*   **Module Code:** `CF-TREE-01`
*   **Topic:** Trees & Hierarchical State Traversal
*   **Level:** Intermediate
*   **Prerequisites:**
    *   `CF-REC-01`: Recursion & Backtracking Mechanics
    *   `CF-STK-01`: Stacks, Queues, and Deques
    *   `CF-CMP-01`: Asymptotic Complexity Analysis ($O(V+E)$, Master Theorem)
*   **Estimated Duration:** 180 Menit (Teori: 60m, Implementasi & Debugging: 75m, Latihan: 45m)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekomposisi** struktur pohon biner (*binary tree*) dan *n-ary tree* bukan sekadar sebagai struktur data statis di memori, melainkan representasi eksplisit dari ruang status percabangan (*branching state-space*).
2.  **Mengidentifikasi dan Menerapkan** paradigma *Top-Down Traversal* (Pre-order / State-passing) dan *Bottom-Up Aggregation* (Post-order / Divide-and-Conquer) untuk menyelesaikan problem kombinatorial dan struktural.
3.  **Mengimplementasikan** empat varian traversal fundamental (*Pre-order, In-order, Post-order, Level-order*) secara rekursif dan iteratif berbasis *explicit call stack/queue* dengan kompleksitas $O(N)$ waktu dan $O(H)$ ruang.
4.  **Mendeteksi dan Memitigasi** anomali struktural seperti *skewed tree* yang menyebabkan degenerasi kompleksitas rekursi dari $O(\log N)$ menjadi $O(N)$, serta risiko *Call Stack Overflow*.
5.  **Merancang** algoritma pelacakan kondisi batas (*boundary conditions*) dan status leluhur bersama (*Lowest Common Ancestor*) dengan invariansi status pohon yang ketat.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [Hierarchical State Space]
                                        │
                ┌───────────────────────┴───────────────────────┐
                ▼                                               ▼
     [Traversal Semantics]                            [State Propagation]
        │               │                                │             │
        ▼               ▼                                ▼             ▼
   [Depth-First]   [Breadth-First]                  [Top-Down]    [Bottom-Up]
   (Pre/In/Post)    (Level-Order)                  (Inheritance) (Aggregation)
        │               │                                │             │
  ┌─────┴─────┐         └──────────────┐                 │             │
  ▼           ▼                        ▼                 │             │
[Recursive] [Iterative]         [Queue-based]            ▼             ▼
 (Implicit)  (Explicit Stack)    (Ring Buffer)      Parameters      Return
                                                    (Context)       Values
```

### Mental Models:
1.  **Pohon sebagai Finite State Machine Bercabang:** Setiap *node* adalah sebuah *state*, dan setiap *edge* adalah transisi *deterministic* berarah tanpa siklus (*Directed Acyclic Graph* dengan derajat masuk $\le 1$).
2.  **Top-Down vs. Bottom-Up Telemetry:** 
    *   *Top-Down* bertindak seperti menyalurkan instruksi/konteks dari akar ke daun (*parameter passing*).
    *   *Bottom-Up* bertindak seperti merangkum laporan/agregasi data dari daun menuju akar (*return value synthesis*).

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pohon (*Tree*) adalah fondasi bagi hampir seluruh sistem komputasi modern dan platform pemecahan masalah algoritma:

1.  **Dunia Nyata (Engineering):**
    *   **Sistem Berkas & DOM:** Representasi dokumen HTML (DOM) dan hierarki direktori UNIX adalah *N-ary trees*.
    *   **Database Indexing:** B-Tree, B+Tree, dan LSM-Trees mengandalkan sifat penyeimbangan pohon untuk pencarian disk-I/O $O(\log N)$.
    *   **Compilers & AST:** Abstract Syntax Tree (AST) digunakan oleh *compiler* (misal: LLVM, V8) untuk optimasi dan generasi kode mesin via *bottom-up post-order reduction*.
2.  **LeetCode & Algorithmic Interviews:**
    *   Kategori *Tree* menduduki >25% dari persoalan teknikal di Big Tech (FAANG/MAMAA).
    *   Merupakan jembatan kognitif wajib menuju *Dynamic Programming on Trees*, *Graph Theory*, dan *Trie Data Structures*.

---

## SEKSI 05 — APA ITU (WHAT)

### Definisi Formal
Secara matematis, sebuah **Tree** $T = (V, E)$ adalah sebuah graf tak-berarah yang terhubung dan tidak memiliki siklus (*connected acyclic graph*), di mana $|E| = |V| - 1$. 

Dalam konteks struktur data pemrograman (Pohon Berakar / *Rooted Tree*):
*   Terdapat tepat satu simpul khusus yang disebut **Root** (Akar).
*   Setiap simpul $u \neq \text{Root}$ memiliki tepat satu simpul induk (*parent*).
*   Simpul-simpul tanpa anak disebut **Leaves** (Daun) atau simpul terminal.

```
       [Root]             Level 0 (Depth 0)
       /    \
     [A]    [B]           Level 1 (Depth 1)
     / \      \
   [C]  [D]   [E]         Level 2 (Depth 2)  <-- Leaves: C, D, E
```

### Varian Binary Tree
1.  **Full Binary Tree:** Setiap simpul memiliki tepat 0 atau 2 anak.
2.  **Complete Binary Tree:** Semua level terisi penuh kecuali mungkin level terakhir, yang terisi rapat dari kiri ke kanan.
3.  **Perfect Binary Tree:** Semua level terisi penuh; jumlah simpul $= 2^{H+1} - 1$ (di mana root memiliki $H = 0$).
4.  **Skewed (Degenerate) Tree:** Setiap simpul induk hanya memiliki 1 anak; struktur merosot ekuivalen menjadi *Singly Linked List* ($H = N$).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Depth-First Search (DFS) & Execution Context

DFS mengeksploitasi struktur LIFO (*Last In, First Out*). Dalam implementasi rekursif, eksekusi dipandu oleh *OS Call Stack*.

```
        ( A )
       /     \
     ( B )   ( C )
```

*   **Pre-order (Node $\to$ Left $\to$ Right):** Aksi dilakukan saat *pertama kali* memasuki simpul. Dipakai untuk kloning struktur pohon atau serialisasi.
*   **In-order (Left $\to$ Node $\to$ Right):** Khusus pada Binary Search Tree (BST), traversal ini menghasilkan urutan nilai yang terurut menaik (*monotonically non-decreasing*).
*   **Post-order (Left $\to$ Right $\to$ Node):** Aksi dilakukan *setelah* seluruh subpohon anak selesai dievaluasi. Wajib digunakan untuk kalkulasi ukuran direktori, penghapusan memori pohon, dan agregasi metrik dari bawah (LCA, Diameter).

### 2. Mekanisme Iteratif (Explicit Stack vs Call Stack)
Untuk menghindari `RecursionError` atau `Stack Overflow` ketika kedalaman $H \ge 10^4$, kita mengganti *call stack* implisit bahasa pemrograman dengan struktur `std::stack` atau `list` pada *heap memory*.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah siklus hidup penelusuran DFS (Pre, In, Post) pada pohon kecil:

```
                  ┌───────┐
                  │ Root  │
                  │   1   │
                  └───┬───┘
              ┌───────┴───────┐
              ▼               ▼
          ┌───────┐       ┌───────┐
          │   2   │       │   3   │
          └───────┘       └───────┘

ALUR JALUR TRAVERSAL (Eulerian Tour):
- Titik masuk pertama: Pre-order
* Titik balik dari anak kiri: In-order
+ Titik keluar terakhir: Post-order

        - (1) --------------------+
         /   \                     \
        /     \                     \
      - (2)    * (1)               + (1)
      /   \                         /
    * (2) + (2)                   - (3)
                                  /   \
                                * (3) + (3)

Urutan Kunjungan:
• Pre-order  (-) : [1, 2, 3]
• In-order   (*) : [2, 1, 3]
• Post-order (+) : [2, 3, 1]
```

### Visualisasi Call Stack Frame Saat Mencapai Simpul Paling Kiri:

```
Memori Tertinggi
┌──────────────────────────────────────────────┐
│ Frame 3: dfs(Node(2)) -> Left child is None  │  <-- Stack Pointer (Top)
├──────────────────────────────────────────────┤
│ Frame 2: dfs(Node(1)) -> Suspended at Left   │
├──────────────────────────────────────────────┤
│ Frame 1: main()                              │
└──────────────────────────────────────────────┘
Memori Terendah (Base of Stack)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi traversal dasar dalam **Python** dan **C++** yang membandingkan pendekatan rekursif vs iteratif eksplisit.

### Definisi Node Bersama:
```python
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
```

```cpp
struct TreeNode {
    int val;
    TreeNode *left;
    TreeNode *right;
    TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}
};
```

### Implementasi Traversal (In-Order Iterative):

#### Python 3:
```python
def inorder_iterative(root: TreeNode) -> list[int]:
    result: list[int] = []
    stack: list[TreeNode] = []
    curr: TreeNode | None = root

    # Invariant: Seluruh node di stack menunggu diproses nilainya 
    # setelah sub-tree kirinya selesai dieksplorasi secara tuntas.
    while curr is not None or stack:
        # Dorong semua cabang kiri ke stack
        while curr is not None:
            stack.append(curr)
            curr = curr.left
        
        # Node teratas tidak memiliki anak kiri lagi yang belum diproses
        curr = stack.pop()
        result.append(curr.val)
        
        # Pindah ke sub-tree kanan
        curr = curr.right

    return result
```

#### C++20:
```cpp
#include <vector>
#include <stack>

std::vector<int> inorderIterative(TreeNode* root) {
    std::vector<int> result;
    std::stack<TreeNode*> st;
    TreeNode* curr = root;

    while (curr != nullptr || !st.empty()) {
        while (curr != nullptr) {
            st.push(curr);
            curr = curr->left;
        }
        curr = st.top();
        st.pop();
        result.push_back(curr->val);
        curr = curr->right;
    }
    return result;
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Studi Kasus: LeetCode 124 — Binary Tree Maximum Path Sum (Hard)
Sebuah *path* pada pohon adalah barisan simpul di mana setiap pasangan simpul bertetangga memiliki *edge* penghubung. Suatu simpul hanya boleh muncul maksimal satu kali dalam sebuah lintasan.

#### Strategi Resolusi (Bottom-Up Post-Order Aggregation):
Untuk setiap simpul $u$, nilai lintasan maksimal yang melintasi $u$ sebagai simpul tertinggi (puncak) adalah:
$$\text{MaxPath}(u) = u.\text{val} + \max(0, \text{Gain}(\text{left})) + \max(0, \text{Gain}(\text{right}))$$
Sementara nilai yang dapat disumbangkan (*gain*) oleh subpohon $u$ ke induknya di atas adalah:
$$\text{Gain}(u) = u.\text{val} + \max(0, \max(\text{Gain}(\text{left}), \text{Gain}(\text{right})))$$

#### Python 3 Implementation:
```python
class Solution:
    def maxPathSum(self, root: TreeNode | None) -> int:
        # Inisialisasi dengan -infinity untuk menangani simpul yang bernilai negatif
        max_global = float('-inf')

        def calculate_gain(node: TreeNode | None) -> int:
            nonlocal max_global
            if not node:
                return 0

            # Post-Order: Dapatkan gain maksimum dari anak kiri dan kanan.
            # Jika gain bernilai negatif, abaikan dengan membatasi ke 0 (pruning).
            left_gain = max(calculate_gain(node.left), 0)
            right_gain = max(calculate_gain(node.right), 0)

            # Harga path lokal jika simpul ini adalah apex/puncak dari belokan path
            current_path_sum = node.val + left_gain + right_gain

            # Perbarui rekor global jika current_path_sum lebih unggul
            max_global = max(max_global, current_path_sum)

            # Kembalikan kontribusi maksimum satu cabang ke node parent
            return node.val + max(left_gain, right_gain)

        calculate_gain(root)
        return int(max_global)
```

#### Kompleksitas:
*   **Waktu:** $O(N)$ — Setiap simpul dikunjungi tepat dua kali (masuk dan keluar).
*   **Ruang:** $O(H)$ — Di mana $H$ adalah tinggi pohon. Pada kasus terburuk (*skewed*) $O(N)$, pada kasus terbaik (*balanced*) $O(\log N)$.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Kompleksitas Waktu | Kompleksitas Ruang | Kelebihan | Kekurangan |
| :--- | :--- | :--- | :--- | :--- |
| **Recursion (Call Stack)** | $O(N)$ | $O(H)$ | Kode sangat ekspresif, intuitif, minim *boilerplate*. | Rawan *StackOverflow* pada Python/Java jika $H > 10^4$. |
| **Explicit Iterative Stack** | $O(N)$ | $O(H)$ | Alokasi memori berada di Heap; kebal terhadap *StackOverflow*. | Kode lebih kompleks (*state* internal harus dimanipulasi manual). |
| **Morris Traversal** | $O(N)$ amortized | $O(1)$ | Tidak membutuhkan memori tambahan sama sekali. | Melakukan modifikasi sementara pada *pointer* pohon (bisa *thread-unsafe*). |
| **BFS (Level-Order / Queue)** | $O(N)$ | $O(W)$ | Sangat optimal mencari jalur terpendek (*unweighted*). | Memori mencapai $O(N/2) = O(N)$ pada level daun terdalam *balanced tree*. |

> *Catatan:* $N$ = Total Simpul, $H$ = Tinggi Pohon ($\log N \le H \le N$), $W$ = Lebar Maksimum Pohon ($1 \le W \le \lceil N/2 \rceil$).

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Null Object / Base Case Guard yang Bersih:**
    Selalu tangani `if not root: return ...` pada baris pertama fungsi rekursif, bukan dengan memvalidasi keberadaan anak sebelum memanggil fungsi:
    ```python
    # BENAR (Clean & Declarative)
    def dfs(node):
        if not node:
            return 0
        return 1 + dfs(node.left) + dfs(node.right)

    # SALAH (Messy & Prone to NullPointerException)
    def dfs(node):
        ans = 1
        if node.left:
            ans += dfs(node.left)
        if node.right:
            ans += dfs(node.right)
        return ans
    ```
2.  **Pemisahan Parameter Top-Down dan Return Bottom-Up:**
    *   Gunakan parameter untuk menyalurkan **syarat batas/restriksi** (contoh: rentang validasi BST `min_val, max_val`).
    *   Gunakan *return value* untuk menyalurkan **hasil kalkulasi/agregasi** (contoh: tinggi subtree, jumlah node, boolean validitas).
3.  **Terapkan Explicit Path Tracking Immutability:**
    Jika merekam jalur daun (*root-to-leaf path*), lakukan *backtracking* eksplisit (`path.pop()`) daripada membuat salinan *array* baru di setiap level rekursi yang menaikkan kompleksitas ruang menjadi $O(N^2)$.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Asumsi Pohon Selalu Seimbang (*Balanced*):**
    Mengasumsikan kompleksitas ruang selalu $O(\log N)$. Penguji LeetCode sering menyertakan kasus uji berupa *degenerate/skewed tree* yang membuat kedalaman rekursi bernilai $N$.
2.  **Kegagalan Penanganan Nilai Negatif:**
    Menginisialisasi variabel pelacak maksimum dengan `0` bukannya `-infinity`. Jika seluruh simpul bernilai negatif (contoh: `[-3, -2, -5]`), hasil kalkulasi akan salah bernilai `0`.
3.  **Kebocoran Referensi pada Rekursi Global:**
    Menggunakan variabel global atau atribut *class* yang tidak di-*reset* antar pemanggilan fungsi test runner LeetCode. Gunakan fungsi penolong (*inner helper function*) yang mengikat variabel dengan `nonlocal` atau referensi pointer eksplisit.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Easy): Invert Binary Tree (LeetCode 226)
*   **Masalah:** Diberikan `root` dari sebuah binary tree, balikkan (*invert*) pohon tersebut dan kembalikan simpul akarnya.
*   **Batasan:** Jumlah node $[0, 100]$, Nilai Node $[-100, 100]$.
*   **Blueprint Solusi:** Lakukan post-order traversal; tukar pointer `left` dan `right` dari setiap node yang dikunjungi.

### Latihan 2 (Medium): Lowest Common Ancestor of a Binary Tree (LeetCode 236)
*   **Masalah:** Temukan simpul leluhur terendah (LCA) dari dua simpul yang ditentukan, `p` dan `q`.
*   **Batasan:** Simpul unik, $p \neq q$, semua nilai simpul berada dalam rentang integer.
*   **Blueprint Solusi:** 
    *   Jika `root == None` atau `root == p` atau `root == q`, kembalikan `root`.
    *   Cari secara rekursif di `root.left` dan `root.right`.
    *   Jika kedua sisi mengembalikan simpul valid, maka `root` saat ini adalah titik temu (LCA).
    *   Jika hanya salah satu, teruskan simpul non-null tersebut ke atas.

### Latihan 3 (Hard): Binary Tree Cameras (LeetCode 968)
*   **Masalah:** Pasang kamera dengan jumlah sesedikit mungkin pada simpul pohon sehingga seluruh simpul terawasi. Kamera mengawasi dirinya, induknya, dan anak langsungnya.
*   **Batasan:** Node count $[1, 1000]$, representasi biner.
*   **Blueprint Solusi:** Terapkan State Machine via Post-order traversal:
    *   Status 0: Node belum tercover.
    *   Status 1: Node terpasang kamera.
    *   Status 2: Node sudah tercover (oleh kamera anaknya).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Pertanyaan:** Jika sebuah pohon biner memiliki $N$ simpul, berapa banyak pointer `nullptr` / `None` yang ada di seluruh pohon tersebut?
    *   *A)* $N - 1$
    *   *B)* $N$
    *   *C)* $N + 1$
    *   *D)* $2N$
2.  **Pertanyaan:** Kapan pemrosesan In-order traversal menghasilkan barisan angka terurut monotonik menaik?
    *   *A)* Pada semua Complete Binary Trees
    *   *B)* Khusus pada Binary Search Trees (BST) yang valid
    *   *C)* Pada Max-Heap
    *   *D)* Pada Full Binary Trees
3.  **Pertanyaan:** Manakah traversal yang paling tepat untuk menghitung total ukuran memori file direktori pada struktur sistem berkas berbasis pohon?
    *   *A)* Pre-order Traversal
    *   *B)* Post-order Traversal
    *   *C)* In-order Traversal
    *   *D)* Breadth-First Search
4.  **Analisis Kode:** Apa *output* dari cuplikan kode Python berikut jika input adalah pohon $1 \to \text{Left: } 2, \text{Right: } 3$?
    ```python
    def f(root):
        if not root: return 0
        l = f(root.left)
        r = f(root.right)
        return max(l, r) + 1
    ```
    *   *Jawaban:* `2` (Fungsi ini menghitung *Height / Maximum Depth* dari pohon).
5.  **Pertanyaan:** Apa kelemahan utama Morris Traversal dibandingkan dengan DFS iteratif konvensional yang memakai stack bantuan?
    *   *A)* Kompleksitas waktu Morris adalah $O(N^2)$.
    *   *B)* Morris membutuhkan struktur data memori $O(N)$ tambahan di heap.
    *   *C)* Morris melakukan mutasi sementara pada link pohon, menyebabkannya tidak *thread-safe* untuk eksekusi konkurensi paralel.

### Kunci Jawaban:
1.  **C** — Setiap node memiliki 2 pointer ($2N$ total pointer). Pohon dengan $N$ node memiliki $N-1$ edge aktif. Sisa pointer null $= 2N - (N - 1) = N + 1$.
2.  **B** — Sifat invarian BST menyatakan $L < Root < R$.
3.  **B** — Ukuran direktori induk tidak bisa dihitung sebelum total ukuran dari seluruh subdirektori (anak) dijumlahkan secara tuntas.
4.  **Tinggi Pohon = 2**.
5.  **C** — Morris memanipulasi *in-order predecessor's right pointer* secara langsung pada struktur pohon di memori.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku:** 
    *   *Introduction to Algorithms (CLRS)*, 4th Edition — Chapter 10 (Elementary Data Structures) & Chapter 12 (Binary Search Trees).
    *   *Algorithms*, 4th Edition by Robert Sedgewick & Kevin Wayne — Section 3.2 (Binary Search Trees).
*   **LeetCode Problem Set Primer:**
    *   LC 104: Maximum Depth of Binary Tree
    *   LC 102: Binary Tree Level Order Traversal
    *   LC 236: Lowest Common Ancestor of a Binary Tree
    *   LC 124: Binary Tree Maximum Path Sum
    *   LC 297: Serialize and Deserialize Binary Tree

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  Pohon adalah graf terhubung asiklik yang bertindak sebagai model matematika utama bagi struktur data berhirarki dan ruang status pemecahan masalah algoritma.
2.  Traversal pohon DFS terbagi menjadi Pre-order, In-order, dan Post-order. Pemilihan urutan ini menentukan kapan aksi lokal dieksekusi terhadap waktu eksplorasi anak-anaknya.
3.  **Top-down traversal** mendistribusikan konteks status dari atas ke bawah menggunakan argumen rekursi, sedangkan **bottom-up traversal** mensintesis hasil pemrosesan anak-anak ke atas menggunakan nilai kembalian (*return values*).
4.  Kompleksitas ruang rekursi ditentukan secara mutlak oleh tinggi pohon ($H$). Kewaspadaan terhadap kasus degenerasi (*skewed tree*) $O(N)$ adalah pembeda utama antara kode amatir dan kode level produksi (*enterprise-grade*).

---

## SEKSI 17 — GLOSARIUM

*   **Subtree:** Pohon yang terdiri dari simpul tertentu beserta seluruh keturunan (*descendants*) di bawahnya.
*   **Depth (Kedalaman):** Jumlah sisi/edge dari akar (*root*) menuju simpul tertentu.
*   **Height (Tinggi):** Jumlah sisi/edge terpanjang dari simpul tertentu menuju daun (*leaf*). Tinggi pohon adalah tinggi dari simpul akar.
*   **Call Stack Frame:** Blok memori pada *stack segment* yang menyimpan konteks eksekusi fungsi, variabel lokal, dan instruksi kembali (*return address*) pemanggilan fungsi rekursif.
*   **Backtracking:** Pola traversal yang secara sistematis menelusuri status dan membatalkan status tersebut (*undo state*) saat kembali ke simpul pemanggil.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Pedagogical Hook:** Mulai pengajaran dengan analogi navigasi berkas di Terminal (`cd ..` adalah backtracking, `ls` adalah observasi status lokal, eksekusi `du -sh` adalah post-order traversal).
*   **Peringatan Mental Block:** Peserta didik sering kali bingung membayangkan alur rekursi. Tekankan aturan: *"Percayai bahwa fungsi rekursif Anda akan mengembalikan jawaban yang benar untuk sub-pohon kiri dan kanan (Recursive Leap of Faith). Fokuskan logika hanya pada apa yang harus dilakukan simpul saat ini dengan kedua nilai kembalian tersebut."*
*   **Live Coding Strategy:** Jangan biarkan siswa langsung mengoding solusi LCA atau Max Path Sum. Paksa mereka menggambar representasi pohon di papan tulis/kertas dan melacak pergerakan nilai return bottom-up secara manual.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **v1.0.0 (2024-03-24):**
    *   Rilis awal modul kurikulum Core-Foundations: Trees & Hierarchical State Traversal.
    *   Penambahan implementasi dual-language (Python 3 & C++20).
    *   Penyertaan analisis teknis LeetCode 124 dan diagram alur rekursif ASCII.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `01-Core-Foundations/CF-STK-01`: Stacks, Queues, and Deques Mechanics
*   **Modul Berikutnya:** `01-Core-Foundations/CF-BST-01`: Binary Search Tree Invariants & Self-Balancing Mechanics
*   **Index Repositori:** `00-Curriculum-Overview/MASTER_ROADMAP.md`