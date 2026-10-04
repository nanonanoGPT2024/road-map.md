# KURIKULUM LEETCODE — KATEGORI 01: CORE FOUNDATIONS
## BAB 10: ADVANCED STRUCTURES & SPECIALIZED PARADIGMS
### MODUL 01: Fenwick Tree (Binary Indexed Tree) & Dynamic Range Query Paradigms

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `CF-ADV-10-01`
* **Nama Modul**: Fenwick Tree (Binary Indexed Tree / BIT) & Dynamic Prefix Paradigms
* **Tingkat Kesulitan**: *Advanced* (Pemberian label: L3 / Hard-Track)
* **Prasyarat Pengetahuan**:
  * Bitwise Manipulation (`AND`, `OR`, `XOR`, Two's Complement arithmetic, Least Significant Bit).
  * Prefix Sum Array (Static Range Sum Queries $O(1)$ query, $O(N)$ update).
  * Recursion & Divide-and-Conquer Mental Models.
* **Estimasi Beban Belajar**: 180–240 menit (Teori, Trace Bitwise, Analisis Kompleksitas, dan 3 Implementasi Algoritmik).
* **Kompatibilitas Bahasa**: C++20, Python 3.11+, Java 17+.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Keterbatasan Struktur Data Statis (Bloom: C4 - Analysis)**: Membedakan titik kegagalan performa antara Prefix Sum Array ($O(1)$ query, $O(N)$ update) dan Naive Array ($O(1)$ update, $O(N)$ query) pada beban kerja dinamis.
2. **Mendekonstruksi Aljabar Bitwise Fenwick Tree (Bloom: C4 - Analysis)**: Menjelaskan derivasi matematis dari isolasi bit terendah (`x & (-x)`) menggunakan representasi *two's complement* dan memetakannya ke rentang interval penanggung jawab.
3. **Mengimplementasikan BIT Dinamis (Bloom: C3 & C5 - Apply & Evaluate)**: Menulis struktur data Fenwick Tree 1-based indexing secara mandiri dengan invariansi ketat untuk operasi Point Update dan Prefix Sum dalam kompleksitas waktu $O(\log N)$ dan ruang $O(N)$.
4. **Menerapkan Pola Kompresi Koordinat (Coordinate Compression) (Bloom: C3 - Apply)**: Mengintegrasikan diskretisasi domain nilai kontinu atau sparse ke dalam ruang diskret $1 \dots M$ guna memitigasi ledakan memori pada BIT.
5. **Memecahkan Masalah Inversion Counting & Dynamic Order Statistics (Bloom: C6 - Create)**: Merancang arsitektur solusi untuk masalah LeetCode Hard (seperti *Count of Smaller Numbers After Self*, *Reverse Pairs*) memanfaatkan kombinasi Fenwick Tree dan Coordinate Compression.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [Range Query Paradigms]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
   [Static Queries]                               [Dynamic Queries]
  (Prefix Sum / Sparse Table)                    (Updates + Queries)
         │                                                 │
         ├─ Static Sum: O(1) Q, O(N) U                     ├─ Naive: O(N) Q / O(1) U
         └─ Static RMQ: O(1) Q, O(N log N) Build           │
                                                           ▼
                                            [Duality Trade-off Bridge]
                                                           │
                        ┌──────────────────────────────────┴────────────────────────────────┐
                        ▼                                                                   ▼
             [Segment Tree (Full)]                                            [Fenwick Tree (BIT)]
     - Struktur: Pohon Biner Eksplisit                                 - Struktur: Array Implisit Berbasis Bit
     - Kapabilitas: Arbitrary Associative Ops                          - Kapabilitas: Invertible Monoid (Sum, XOR)
     - Overhead: 4N Memory, High Constant Factor                       - Overhead: 1N Memory, Extremely Low Constant
                        │                                                                   │
                        └──────────────────────────┬────────────────────────────────────────┘
                                                   ▼
                                       [Operasi Inti Fenwick]
                                                   │
                         ┌─────────────────────────┴─────────────────────────┐
                         ▼                                                   ▼
                [Isolasi LSB: x & (-x)]                            [Transversal Pohon]
                         │                                                   │
                         ├─ update(idx, val): idx += LSB(idx)                ├─ Point Update, Range Query
                         └─ query(idx):       idx -= LSB(idx)                └─ Range Update, Point Query (Diff Array)
                                                                             │
                                                                             ▼
                                                                 [Aplikasi Tingkat Lanjut]
                                                                             │
                                                                             ├─ Inversion Counting (LeetCode 315)
                                                                             ├─ Coordinate Compression (Discretization)
                                                                             └─ 2D Range Queries
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem skala besar dan permasalahan *algorithmic trading* maupun *competitive programming*, data jarang bersifat statis. Pertimbangkan skenario berikut:

| Struktur Data | Kompleksitas Update | Kompleksitas Range Sum Query | Ruang Tambahan | Faktor Konstanta (*Cache Locality*) |
| :--- | :--- | :--- | :--- | :--- |
| **Array Biasa** | $O(1)$ | $O(N)$ | $O(1)$ | Sangat Cepat |
| **Prefix Sum Array** | $O(N)$ | $O(1)$ | $O(N)$ | Sangat Cepat |
| **Segment Tree** | $O(\log N)$ | $O(\log N)$ | $O(4N)$ | Sedang (Pointers/Tree-traversal) |
| **Fenwick Tree (BIT)**| $\mathbf{O(\log N)}$ | $\mathbf{O(\log N)}$ | $\mathbf{O(N)}$ | **Sangat Cepat (Flat Array contiguous memory)** |

Jika sebuah skenario membutuhkan $M$ operasi pembaruan (*updates*) dan $Q$ operasi pembacaan interval (*range queries*), di mana $M, Q \le 10^5$:
* Menggunakan **Prefix Sum**: Total waktu $O(M \cdot N + Q \cdot 1) \approx 10^{10}$ operasi $\rightarrow$ **Time Limit Exceeded (TLE)**.
* Menggunakan **Naive Array**: Total waktu $O(M \cdot 1 + Q \cdot N) \approx 10^{10}$ operasi $\rightarrow$ **Time Limit Exceeded (TLE)**.
* Menggunakan **Fenwick Tree**: Total waktu $O((M + Q) \log N) \approx 2 \cdot 10^5 \cdot 17 \approx 3.4 \times 10^6$ operasi $\rightarrow$ **Dieksekusi dalam $< 0.05$ detik**.

Fenwick Tree menawarkan kode yang 3 kali lebih ringkas dibanding Segment Tree standar tanpa representasi rekursif, menjadikannya senjata paling efisien di wawancara teknis (FAANG/Tier-1) saat berhadapan dengan masalah agregasi prefix dinamis.

---

## SEKSI 05 — APA ITU (WHAT)

**Fenwick Tree** (ditemukan oleh Peter M. Fenwick pada tahun 1994) adalah struktur data berbasis array satu dimensi yang merepresentasikan pohon implisit tanpa pointer eksplisit. Tujuannya adalah menghitung jumlah prefiks (*prefix sums*) dan memperbarui nilai elemen secara dinamis dalam waktu logaritmik.

### 1. Fondasi Matematis: Least Significant Bit (LSB)
Kunci arsitektural dari Fenwick Tree adalah panjang interval yang dikelola oleh indeks $i$. Setiap indeks $i$ bertanggung jawab atas rentang elemen sebanyak:
$$\text{length}(i) = \text{LSB}(i) = i \ \& \ (-i)$$

Secara biner pada mesin modern, bilangan bulat bertanda direpresentasikan menggunakan komplemen dua (*two's complement*):
$$-x = (\sim x) + 1$$

Ketika operasi bitwise AND diterapkan antara $x$ dan $-x$:
1. Semua bit di sebelah kiri bit `1` paling rendah akan terbalik pada $\sim x$, dan bit di sebelah kanan adalah `0`.
2. Penambahan `1` merambatkan carry dari posisi bit paling kanan hingga berhenti tepat di posisi bit `1` terendah asli milik $x$.
3. Operasi $x \ \& \ (-x)$ mempertahankan tepat satu bit `1`, yaitu LSB dari $x$.

*Contoh Numerik:*
* $x = 12_{10} = 00001100_2$
* $-x = -12_{10} = 11110011_2 + 1 = 11110100_2$
* $x \ \& \ (-x) = 00001100_2 \ \& \ 11110100_2 = 00000100_2 = 4_{10}$

Maka, elemen pada array tree `BIT[12]` memegang tanggung jawab agregasi untuk $4$ elemen berakhir di indeks 12, yaitu interval $[12 - 4 + 1, 12] = [9, 12]$.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Fenwick Tree secara konseptual menggunakan **1-based indexing** demi mempermudah manipulasi LSB (karena $\text{LSB}(0) = 0$, yang akan memicu *infinite loop*).

### 1. Mekanisme Query (Prefix Sum $1 \dots i$)
Untuk menghitung $\sum_{k=1}^{i} A[k]$:
1. Mulai dari indeks $i$.
2. Akumulasikan nilai `tree[i]` ke variabel `sum`.
3. Kurangi $i$ dengan LSB-nya: $i = i - (i \ \& \ (-i))$.
4. Ulangi hingga $i = 0$.

Proses ini membongkar bilangan $i$ menjadi jumlahan dari perpangkatan dua (representasi biner uniknya). Karena representasi biner sebuah bilangan $N$ memiliki maksimal $\lfloor \log_2 N \rfloor + 1$ bit `1`, loop berjalan paling banyak $O(\log N)$ kali.

### 2. Mekanisme Update (Point Update: Tambahkan $\Delta$ pada indeks $i$)
Ketika elemen asli $A[i]$ ditambah $\Delta$:
1. Mulai dari indeks $i$.
2. Tambahkan $\Delta$ pada `tree[i]`.
3. Lompat ke simpul leluhur (*ancestor node*) yang mencakup indeks $i$, yaitu: $i = i + (i \ \& \ (-i))$.
4. Ulangi hingga $i > N$.

Setiap penambahan LSB mengubah bit `1` terendah menjadi `0` dan merambat ke atas, mengunjungi seluruh interval penampung dalam $O(\log N)$ langkah.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah peta dekomposisi interval untuk ukuran array $N = 8$:

```
Indeks (Biner) | Interval yang Dicakup | Visualisasi Cakupan Elemen (1 s.d. 8)
---------------+-----------------------+-------------------------------------------------------
1  (0001)      | [1, 1]                | [1]
2  (0010)      | [1, 2]                | [1───────2]
3  (0011)      | [3, 3]                |             [3]
4  (0100)      | [1, 4]                | [1───────────────────4]
5  (0101)      | [5, 5]                |                         [5]
6  (0110)      | [5, 6]                |                         [5───────6]
7  (0111)      | [7, 7]                |                                     [7]
8  (1000)      | [1, 8]                | [1───────────────────────────────────────────8]
```

### Jalur Query Prefix Sum untuk $i = 7$:
$$7_{10} = 0111_2 \xrightarrow{-1} 6_{10} = 0110_2 \xrightarrow{-2} 4_{10} = 0100_2 \xrightarrow{-4} 0$$

```
   Query(7):
   ambil tree[7]  (mencakup [7, 7])
        │
        ▼ (7 - LSB(7) = 7 - 1 = 6)
   ambil tree[6]  (mencakup [5, 6])
        │
        ▼ (6 - LSB(6) = 6 - 2 = 4)
   ambil tree[4]  (mencakup [1, 4])
        │
        ▼ (4 - LSB(4) = 4 - 4 = 0) -> Selesai.
   Total Sum = tree[7] + tree[6] + tree[4] == sum(A[1..7])
```

### Jalur Update Point untuk $i = 3$:
$$3_{10} = 0011_2 \xrightarrow{+1} 4_{10} = 0100_2 \xrightarrow{+4} 8_{10} = 1000_2 \xrightarrow{+8} 16 > N$$

```
   Update(3, +val):
   tambah ke tree[3]  (mencakup index 3)
        │
        ▼ (3 + LSB(3) = 3 + 1 = 4)
   tambah ke tree[4]  (mencakup index 1..4)
        │
        ▼ (4 + LSB(4) = 4 + 4 = 8)
   tambah ke tree[8]  (mencakup index 1..8)
        │
        ▼ (8 + LSB(8) = 8 + 8 = 16 > 8) -> Selesai.
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi struktur kelas Fenwick Tree standar industri menggunakan C++20 untuk memecahkan problem dasar Range Sum Query (LeetCode 307: *Range Sum Query - Mutable*).

```cpp
#include <vector>
#include <stdexcept>

class FenwickTree {
private:
    int size;
    std::vector<long long> tree;

    // Menghitung LSB (Least Significant Bit)
    static inline int lsb(int x) {
        return x & (-x);
    }

public:
    // Konstruktor: Inisialisasi tree dengan ukuran n (1-based index)
    explicit FenwickTree(int n) : size(n), tree(n + 1, 0) {}

    // Konstruktor dengan linear build O(N)
    explicit FenwickTree(const std::vector<int>& nums) : size(nums.size()), tree(nums.size() + 1, 0) {
        for (int i = 1; i <= size; ++i) {
            tree[i] += nums[i - 1];
            int parent = i + lsb(i);
            if (parent <= size) {
                tree[parent] += tree[i];
            }
        }
    }

    // Menambahkan delta pada indeks idx (1-based)
    void add(int idx, long long delta) {
        if (idx <= 0 || idx > size) {
            throw std::out_of_range("Index out of bounds pada FenwickTree::add");
        }
        for (; idx <= size; idx += lsb(idx)) {
            tree[idx] += delta;
        }
    }

    // Mengambil prefix sum dari [1 ... idx]
    [[nodiscard]] long long query(int idx) const {
        if (idx < 0) return 0;
        if (idx > size) idx = size;
        long long sum = 0;
        for (; idx > 0; idx -= lsb(idx)) {
            sum += tree[idx];
        }
        return sum;
    }

    // Mengambil range sum dari [left ... right] (1-based)
    [[nodiscard]] long long queryRange(int left, int right) const {
        if (left > right) return 0;
        return query(right) - query(left - 1);
    }
};
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Masalah Algoritmik: LeetCode 315 — *Count of Smaller Numbers After Self*
*Deskripsi*: Diberikan array integer `nums`, kembalikan array `counts` di mana `counts[i]` adalah banyaknya elemen `nums[j]` dengan $j > i$ sedemikian rupa sehingga `nums[j] < nums[i]`.

*Kendala*:
* $1 \le \text{nums.length} \le 10^5$
* $-10^4 \le \text{nums}[i] \le 10^4$

### Analisis & Pola Solusi:
1. Jika kita memproses elemen dari **kanan ke kiri**, semua elemen yang telah kita lihat sejauh ini berada di sebelah kanan posisi saat ini ($j > i$).
2. Pertanyaan berubah menjadi: *"Berapa banyak elemen yang telah dilihat sejauh ini yang nilainya $< nums[i]$?"*
3. Ini adalah masalah pembacaan frekuensi prefix dinamis: `query(nums[i] - 1)`.
4. Setelah mengambil jawaban untuk `nums[i]`, kita masukkan `nums[i]` ke dalam struktur data dengan `add(nums[i], 1)`.
5. Karena nilai `nums[i]` bisa bernilai negatif ($-10^4$), kita harus menerapkan **Coordinate Compression (Diskretisasi)** atau transformasi translasi nilai ke indeks positif $[1, M]$.

### Implementasi Lengkap (Python 3):

```python
from typing import List

class FenwickTree:
    def __init__(self, size: int):
        self.size = size
        self.tree = [0] * (size + 1)

    def add(self, idx: int, delta: int) -> None:
        """Tambahkan delta pada elemen frekuensi di index idx (1-based)."""
        while idx <= self.size:
            self.tree[idx] += delta
            idx += idx & (-idx)

    def query(self, idx: int) -> int:
        """Ambil total frekuensi kumulatif dari 1 hingga idx."""
        total = 0
        while idx > 0:
            total += self.tree[idx]
            idx -= idx & (-idx)
        return total

class Solution:
    def countSmaller(self, nums: List[int]) -> List[int]:
        if not nums:
            return []

        # Langkah 1: Coordinate Compression (Diskretisasi)
        # Menghapus duplikat dan mengurutkan elemen unik
        sorted_unique = sorted(set(nums))
        # Petakan setiap nilai ke peringkat 1-based (ranks: 1 ... M)
        ranks = {val: idx + 1 for idx, val in enumerate(sorted_unique)}
        max_rank = len(sorted_unique)

        bit = FenwickTree(max_rank)
        result = [0] * len(nums)

        # Langkah 2: Proses dari Kanan ke Kiri
        for i in range(len(nums) - 1, -1, -1):
            rank = ranks[nums[i]]
            # Ambil frekuensi elemen yang bernilai LEBIH KECIL dari nilai sekarang
            # Yaitu akumulasi frekuensi dari rank 1 s.d. (rank - 1)
            result[i] = bit.query(rank - 1)
            
            # Daftarkan elemen saat ini ke dalam BIT
            bit.add(rank, 1)

        return result
```

### Dry Run Singkat:
* `nums = [5, 2, 6, 1]`
* Unik terurut: `[1, 2, 5, 6]` $\rightarrow$ Mapping Ranks: `{1: 1, 2: 2, 5: 3, 6: 4}`
* Iterasi $i=3$ (`nums[3] = 1`, `rank = 1`):
  * `query(0) = 0` $\rightarrow$ `result[3] = 0`
  * `add(1, 1)` $\rightarrow$ BIT mencatat rank 1 muncul 1x.
* Iterasi $i=2$ (`nums[2] = 6`, `rank = 4`):
  * `query(3)` $\rightarrow$ mengambil frekuensi rank 1..3 = $1$. `result[2] = 1`
  * `add(4, 1)` $\rightarrow$ BIT mencatat rank 4 muncul 1x.
* Iterasi $i=1$ (`nums[1] = 2`, `rank = 2`):
  * `query(1)` $\rightarrow$ mengambil frekuensi rank 1 = $1$. `result[1] = 1`
  * `add(2, 1)` $\rightarrow$ BIT mencatat rank 2 muncul 1x.
* Iterasi $i=0$ (`nums[0] = 5`, `rank = 3`):
  * `query(2)` $\rightarrow$ mengambil frekuensi rank 1..2 = $2$. `result[0] = 2`
  * `add(3, 1)`
* Output akhir: `[2, 1, 1, 0]`. Tepat dan terbukti matematis.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Memilih antara Fenwick Tree dan alternatif struktur rentang lainnya membutuhkan analisis batasan masalah:

| Dimensi | Fenwick Tree | Segment Tree | Sparse Table | Sqrt Decomposition |
| :--- | :--- | :--- | :--- | :--- |
| **Waktu Pembangunan** | $O(N)$ | $O(N)$ | $O(N \log N)$ | $O(N)$ |
| **Point Update** | $O(\log N)$ | $O(\log N)$ | Non-trivial / $O(N)$ | $O(1)$ |
| **Range Sum Query** | $O(\log N)$ | $O(\log N)$ | $O(\log N)$ | $O(\sqrt{N})$ |
| **Range Min/Max Query**| Sulit ($O(\log^2 N)$)* | $O(\log N)$ | $\mathbf{O(1)}$ *(Idempotent)*| $O(\sqrt{N})$ |
| **Konsumsi Memori** | $\mathbf{1 \times N}$ *(Array asli)* | $4 \times N$ *(Array)* | $N \log N$ | $N + \sqrt{N}$ |
| **Overhead Kode** | ~15-20 baris kode | ~60-100 baris kode | ~25 baris kode | ~40 baris kode |
| **Cache Locality** | **Sangat Baik** | Kurang Baik | Baik | Baik |

*\*Catatan*: Fenwick Tree mengandalkan **operasi invertibel** (seperti penjumlahan dengan pengurangan, XOR dengan XOR). Untuk operasi non-invertibel seperti `Range Minimum Query (RMQ)` atau `Range GCD`, Segment Tree atau Sparse Table jauh lebih unggul karena Fenwick Tree membutuhkan trik traversal khusus yang merusak kompleksitas waktu optimalnya jika ada operasi update dinamis.

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Konstruksi Linear $O(N)$, Bukan $O(N \log N)$**:
   Jangan menginisialisasi Fenwick Tree dengan memanggil `add()` sebanyak $N$ kali berturut-turut ($O(N \log N)$). Dorong nilai parsial ke simpul *parent* secara langsung dalam satu lintasan linear $O(N)$:
   ```cpp
   for (int i = 1; i <= n; ++i) {
       int parent = i + (i & (-i));
       if (parent <= n) tree[parent] += tree[i];
   }
   ```
2. **Karantina Logika 1-Based Indexing**:
   Jangan biarkan logika 1-based indexing bocor ke lapisan antarmuka aplikasi publik. Bungkus konversi `idx + 1` di dalam implementasi method API untuk mencegah kesalahan *off-by-one*.
3. **Selalu Gunakan 64-bit Integer (`long long` / `int64_t`) untuk Akumulasi**:
   Penjumlahan berkali-kali pada array integer dengan panjang $10^5$ dan nilai elemen $10^9$ akan langsung menyebabkan *integer overflow* ($32$-bit bertanda meluap pada $\approx 2 \times 10^9$). Selalu gunakan penampung $64$-bit untuk array internal tree.
4. **Pola Range Update & Point Query via Perbedaan Nilai (Difference Array)**:
   Jika masalah membutuhkan *Range Update* $[L, R] += \Delta$ dan *Point Query* di indeks $K$, alih-alih menggunakan Segment Tree berlapis *Lazy Propagation*, gunakan Fenwick Tree atas **Difference Array** $D[i] = A[i] - A[i-1]$:
   * Update $[L, R]$ dengan $\Delta$: Panggil `add(L, delta)` dan `add(R + 1, -delta)`.
   * Point Query pada $K$: Panggil `query(K)`.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Infinite Loop Akibat Eksekusi `LSB(0)`**:
   * *Kesalahan*: Memanggil `query(0)` atau `add(0, val)`.
   * *Analisis*: `0 & (-0) = 0`. Maka loop `idx += lsb(idx)` atau `idx -= lsb(idx)` akan terus menghasilkan $0$, memicu loop tak berujung (*infinite loop*) yang berujung pada TLE / OOM crash.
   * *Solusi*: Selalu validasi $idx \ge 1$.
2. **Lupa Menerapkan Coordinate Compression**:
   * *Kesalahan*: Menggunakan nilai asli $nums[i] = 10^9$ langsung sebagai indeks Fenwick Tree `tree[nums[i]]`.
   * *Dampak*: Kegagalan alokasi memori berukuran miliaran elemen (*Memory Limit Exceeded* atau `std::bad_alloc`).
   * *Solusi*: Urutkan dan petakan elemen unik ke indeks rank rentang $[1, K]$ di mana $K \le N$.
3. **Salah Mengurangkan Range Query**:
   * *Kesalahan*: Menghitung $\text{Sum}[L, R]$ sebagai `query(R) - query(L)`.
   * *Dampak*: Elemen pada indeks $L$ ikut terkurang secara keliru.
   * *Koreksi*: Range query yang benar adalah `query(R) - query(L - 1)`.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Warm-up / Easy-Medium)
* **Masalah**: Buatlah class `NumArray` yang menerima array dinamis integer, mengimplementasikan method `update(index, val)` dan `sumRange(left, right)`. (LeetCode 307).
* **Target Kompleksitas**: Inisialisasi $O(N)$, Update $O(\log N)$, Query $O(\log N)$, Space $O(N)$.
* **Bimbingan**: Simpan salinan array asli `nums` untuk menghitung $\Delta = val - nums[index]$ sebelum memanggil `add(index + 1, delta)`.

### Latihan 2 (Intermediate)
* **Masalah**: Diberikan array $A$, cari jumlah pasangan terbalik (*inversions*) sedemikian rupa sehingga $i < j$ dan $A[i] > A[j]$.
* **Target Kompleksitas**: $O(N \log N)$ Time, $O(N)$ Space.
* **Bimbingan**: Gunakan teknik pemrosesan dari kanan ke kiri atau kiri ke kanan dengan Coordinate Compression.

### Latihan 3 (Advanced / Hard)
* **Masalah**: LeetCode 493 — *Reverse Pairs*. Diberikan array `nums`, kembalikan jumlah pasangan penting yang terbalik sedemikian rupa sehingga $i < j$ dan $nums[i] > 2 \cdot nums[j]$.
* **Tantangan**: Karena relasi melibatkan pengali $2$, diskretisasi harus mencakup himpunan gabungan: $\text{Unique}(nums \cup \{2 \cdot x \mid x \in nums\})$.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji pemahaman Anda:

1. **Berapa banyak elemen yang dicakup oleh simpul indeks $48$ pada Fenwick Tree?**
   * A. 16 elemen
   * B. 32 elemen
   * C. 48 elemen
   * D. 8 elemen
   * *Jawaban*: **A**. $48_{10} = 32 + 16 = 00110000_2$. $\text{LSB}(48) = 00010000_2 = 16$. Jadi, interval mencakup 16 elemen ($[33, 48]$).

2. **Kapan Fenwick Tree TIDAK BISA menggantikan Segment Tree?**
   * A. Menghitung Prefix Sum dinamis.
   * B. Range Minimum Query (RMQ) dengan pembaruan dinamis berkali-kali.
   * C. Menghitung jumlah inversi secara dinamis.
   * D. Melakukan Point Update dan Range Sum Query.
   * *Jawaban*: **B**. Fenwick Tree dirancang untuk struktur aljabar monoid invertibel. Operator `min(a, b)` tidak bersifat invertibel (tidak dapat membatalkan `min` dengan invers pengurangan).

3. **Berapa jumlah maksimum iterasi loop yang dilakukan pada pemanggilan `query(1023)`?**
   * A. 1024
   * B. 512
   * C. 10
   * D. 1
   * *Jawaban*: **C**. $1023_{10} = 1111111111_2$ (memiliki sepuluh bit `1`). Setiap langkah `idx -= lsb(idx)` mematikan tepat satu bit `1`. Total lompatan: 10 langkah.

4. **Operasi bitwise `x & (-x)` pada arsitektur komplemen dua menghasilkan:**
   * A. Most Significant Bit dari $x$.
   * B. Least Significant Bit bernilai 1 dari $x$.
   * C. Nilai mutlak dari $x$.
   * D. Komplemen satu dari $x$.
   * *Jawaban*: **B**.

5. **Apa fungsi dari array kompresi koordinat (Coordinate Compression) dalam integrasi Fenwick Tree?**
   * A. Mengurangi kompleksitas waktu dari $O(\log N)$ ke $O(1)$.
   * B. Memetakan rentang nilai yang sangat besar atau negatif ke dalam rentang indeks diskret $[1, N]$ yang muat di memori.
   * C. Menghindari floating point error.
   * D. Mengizinkan implementasi 0-based indexing.
   * *Jawaban*: **B**.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Makalah Asli**: Fenwick, Peter M. (1994). *"A New Data Structure for Cumulative Frequency Tables"*. Software: Practice and Experience, 24(3): 327–336.
2. **Kompilasi Algoritma Kompetitif**:
   * *CP-Algorithms*: Fenwick Tree (Binary Indexed Tree) Theory & Range Updates.
   * Antti Laaksonen. *Competitive Programmer's Handbook* (Chapter 9: Range Queries).
3. **Problem Set Terkurasi (LeetCode)**:
   * LeetCode 307: *Range Sum Query - Mutable* (Medium)
   * LeetCode 315: *Count of Smaller Numbers After Self* (Hard)
   * LeetCode 493: *Reverse Pairs* (Hard)
   * LeetCode 327: *Count of Range Sum* (Hard)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
=============================================================================
                      FENWICK TREE QUICK-REFERENCE CHEAT SHEET
=============================================================================
1. Formula Kunci LSB       : LSB(x) = x & (-x)
2. Operasi Query Prefix    : for (; idx > 0; idx -= (idx & -idx)) sum += tree[idx];
3. Operasi Point Update    : for (; idx <= N; idx += (idx & -idx)) tree[idx] += delta;
4. Linear Build O(N)       : tree[i + LSB(i)] += tree[i] (jika i + LSB(i) <= N)
5. Range Query [L, R]      : query(R) - query(L - 1)
6. Range Update (via Diff) : add(L, +V), add(R + 1, -V) -> point query via query(K)
7. Batasan Kritis          : Indeks WAJIB 1-based; Hindari query(0) -> Infinite Loop!
=============================================================================
```

---

## SEKSI 17 — GLOSARIUM

* **Least Significant Bit (LSB)**: Bit bernilai `1` dengan bobot perpangkatan dua terendah dalam representasi biner sebuah bilangan.
* **Two's Complement**: Sistem representasi bilangan bulat bertanda pada komputer biner di mana bilangan negatif didapat dari membalik semua bit lalu ditambah 1.
* **Invertible Operation**: Operasi matematika yang memiliki fungsi kebalikan unik (misalnya penjumlahan memiliki pengurangan, XOR memiliki XOR itu sendiri).
* **Coordinate Compression**: Teknik transformasi memetakan himpunan nilai sparse atau bernilai masif ke dalam himpunan indeks ordinal padat berukuran kecil tanpa merusak relasi urutan relatifnya.
* **Inversion**: Pasangan indeks $(i, j)$ sedemikian rupa sehingga $i < j$ namun $A[i] > A[j]$.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedagogi Visualisasi**: Saat menjelaskan di papan tulis, **jangan langsung menggambar pohon biner standar**. Gambarlah garis lurus interval array yang saling bertumpuk (seperti balok penggaris) untuk menunjukkan bahwa `tree[8]` menumpuk di atas `tree[4]`, `tree[6]`, dan `tree[7]`. Ini jauh lebih cepat dipahami dibanding analogi pointer simpul.
* **Pemberian Hint di Sesi Interview**:
  * Jika kandidat mengusulkan Merge Sort untuk *Inversion Count*, apresiasi kompleksitasnya ($O(N \log N)$). 
  * Lalu tantang: *"Bagaimana jika nilai elemen terus bertambah secara streaming satu per satu secara online?"* Ini adalah pemicu langsung kandidat beralih ke Fenwick Tree.
* **Jebakan Pewawancara**: Perhatikan kandidat yang mengabaikan tipe data numerik saat menghitung jumlah inversi. Total inversi pada array panjang $10^5$ dapat mencapai $\frac{10^5 \times (10^5 - 1)}{2} \approx 5 \times 10^9$, yang meluap dari batas tipe $32$-bit integer bertanda. Tegaskan penggunaan tipe $64$-bit integer.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.1.0 (Current)**:
  * Penambahan skema konstruksi linear $O(N)$ Fenwick Tree.
  * Elaborasi matematis komplementasi dua untuk isolasi LSB.
  * Penyempurnaan kode implementasi LeetCode 315 dengan Python 3 idiomatis dan C++20 standard pada LeetCode 307.
* **Versi 1.0.0**: Inisialisasi modul standar format 20 seksi untuk Fenwick Tree.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CF-TRE-09-04` — Lowest Common Ancestor & Tree Flattening
* **Modul Saat Ini**: `CF-ADV-10-01` — Fenwick Tree (Binary Indexed Tree) & Dynamic Range Query Paradigms
* **Modul Berikutnya**: `CF-ADV-10-02` — Segment Tree Foundations: Point Updates, Range Queries, and Dynamic Discretization