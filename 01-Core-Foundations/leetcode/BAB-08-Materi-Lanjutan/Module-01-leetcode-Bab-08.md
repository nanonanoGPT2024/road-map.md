# Kurikulum LeetCode: 01-Core-Foundations
## Bab 08 Module 01: Binary Search — Invarian Batas, Predikat Monotonik, dan Search Space Reduction

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengidentifikasi karakteristik **monotonisitas** dalam struktur data maupun ruang solusi (*answer space*) abstrak.
- Merancang dan membuktikan kebenaran **Loop Invariant** untuk mencegah *off-by-one error* dan *infinite loop*.
- Mengimplementasikan varian **Lower Bound** (`bisect_left`) dan **Upper Bound** (`bisect_right`) secara deterministik.
- Mentransformasikan masalah optimasi $O(N)$ menjadi evaluasi predikat biner teroptimasi $O(\log(\text{range}) \times \text{cost})$.

---

### 2. Prerequisite
- Pemahaman pointer dan referensi memori contiguous (Array/Vector).
- Analisis kompleksitas asimtotik waktu dan ruang ($O(1)$, $O(N)$, $O(\log N)$).
- Penanganan tipe data primitif dan pencegahan *arithmetic integer overflow* pada level arsitektur CPU.

---

### 3. Concept
Binary Search pada intinya bukanlah algoritma pencarian elemen array semata, melainkan teknik reduksi ruang pencarian (*search space reduction*) berdasar **Predikat Boolean Monotonik** $P(x) \to \{\text{False}, \text{True}\}$.

Jika sebuah domain terurut $S$ dipetakan oleh predikat $P$ sehingga memenuhi urutan:
$$\underbrace{F, F, F, \dots, F}_{\text{False}}, \underbrace{T, T, T, \dots, T}_{\text{True}}$$
Tujuan Binary Search adalah mencari titik transisi:
1. Elemen **pertama** di mana $P(x) = \text{True}$ (*First True* / Lower Bound).
2. Elemen **terakhir** di mana $P(x) = \text{False}$ (*Last False*).

Kunci stabilitas Binary Search terletak pada **Loop Invariant**, yaitu kondisi logika yang harus bernilai benar pada tiga fase eksekusi:
1. **Initialization:** Benar sebelum iterasi pertama dimulai.
2. **Maintenance:** Tetap benar setelah setiap pembaruan batas (*boundary update*).
3. **Termination:** Menjamin bahwa saat loop berakhir, pointer menunjuk ke indeks solusi yang valid tanpa ambiguitas.

---

### 4. Why
1. **Efisiensi Skala Ekstrem:** Memangkas himpunan data berukuran $N = 10^9$ elemen menjadi maksimal 30 kali evaluasi komparasi.
2. **Optimasi Ruang Solusi (*Binary Search on Answer*):** Mengubah problem verifikasi kompleksitas tinggi menjadi pemindaian nilai optimal dengan membagi domain jawaban secara biner.
3. **Pondasi Arsitektur Database & Storage Engine:** Merupakan dasar algoritma traversal pada B+ Tree page index, SSTable index lookups pada RocksDB, dan distributed log index lookup pada Apache Kafka.

---

### 5. What
Komponen utama dalam Binary Search yang teruji:
- **Search Space Interval $[L, R]$:** Rentang indeks atau nilai yang dijamin memuat jawaban.
  - *Closed Interval* $[L, R]$: Loop berjalan selama $L \le R$.
  - *Half-Open Interval* $[L, R)$: Loop berjalan selama $L < R$.
- **Midpoint Calculation:** Kalkulasi titik tengah yang kebal terhadap *integer overflow*:
  $$\text{mid} = L + \left\lfloor\frac{R - L}{2}\right\rfloor$$
- **Monotonic Predicate Function:** Fungsi $P(\text{mid})$ yang mengembalikan nilai boolean tanpa *side-effects*.
- **Boundary Shrinking Logic:** Pembaruan pointer ($L = \text{mid} + 1$ atau $R = \text{mid} - 1$) yang secara ketat menjamin terminasi loop.

---

### 6. How
Berikut adalah alur perancangan Binary Search berbasis predikat:

```
[Mulai]
   │
   ▼
Definisikan Rentang Invariant: [L, R]
   │
   ▼
Apakah L <= R ? ──(False)──> [Solusi = L atau R (Sesuai Invariant)] ──> [Selesai]
   │
 (True)
   │
   ▼
Hitung: mid = L + (R - L) // 2
   │
   ▼
Evaluasi Predikat P(mid)
  ├── True  ──> Jawaban ada di mid atau sebelah kiri: R = mid - 1
  └── False ──> Jawaban mutlak di sebelah kanan:      L = mid + 1
   │
   └─── Mengulang siklus evaluasi
```

---

### 7. Analogy
Bayangkan proses *debugging* regresi kode menggunakan `git bisect`.
Anda memiliki commit sejarah dari commit `0` hingga `1000`. Commit awal berfungsi normal (`False`), namun commit terbaru mengalami *crash* (`True`).
Anda tidak menguji commit satu per satu dari `0` ke `1000` (Linear Scan). Anda menguji commit `500`. Jika commit `500` rusak, maka commit pertama yang memperkenalkan *bug* pasti berada di antara rentang `0` hingga `500`. Anda secara berulang membelah dua commit hingga menemukan commit tunggal penyebab regresi.

---

### 8. Diagram
Visualisasi pembagian ruang pencarian Lower Bound pada array yang terpetakan ke nilai Boolean:

```
Index:       0      1      2      3      4      5      6      7
Array:     [ 2,     3,     5,     7,     8,    10,    12,    15 ]
Predicate:  F      F      F      T      T      T      T      T
(Target: >= 7)                   ▲
                                 │
                         First True (Index 3)

Iterasi 1:
L=0, R=7 -> mid=3 -> Array[3] = 7 (>= 7 ? True)
Simpan potensi solusi, persempit ke kiri: R = mid - 1 (R=2)

Iterasi 2:
L=0, R=2 -> mid=1 -> Array[1] = 3 (>= 7 ? False)
Solusi bukan di kiri: L = mid + 1 (L=2)

Iterasi 3:
L=2, R=2 -> mid=2 -> Array[2] = 5 (>= 7 ? False)
Solusi bukan di kiri: L = mid + 1 (L=3)

Terminasi: L (3) > R (2) -> Return L = 3
```

---

### 9. Simple Example
Implementasi kanonikal Lower Bound (*First element* $\ge \text{target}$) menggunakan Python 3 dengan pengetikan statis:

```python
from typing import List

def lower_bound(nums: List[int], target: int) -> int:
    """
    Mengembalikan indeks elemen pertama yang bernilai >= target.
    Jika semua elemen < target, mengembalikan len(nums).
    Invariant: Jawaban selalu berada dalam rentang [left, right + 1].
    """
    left: int = 0
    right: int = len(nums) - 1
    
    while left <= right:
        # Menghindari integer overflow pada bahasa berbasis tipe data fixed-width
        mid: int = left + (right - left) // 2
        
        if nums[mid] >= target:
            # mid memenuhi kriteria, cari indeks lebih kecil di sisi kiri
            right = mid - 1
        else:
            # nums[mid] < target, solusi mutlak berada di sisi kanan
            left = mid + 1
            
    return left
```

---

### 10. Practical Example
**Kasus LeetCode 875: Koko Eating Bananas (Pencarian Biner pada Ruang Jawaban)**

Koko memakan pisang dari tumpukan `piles`. Dia harus menghabiskan seluruh pisang dalam waktu `h` jam. Kita harus mencari nilai minimum kecepatan makan $k$ (pisang/jam).

```python
import math
from typing import List

class Solution:
    def minEatingSpeed(self, piles: List[int], h: int) -> int:
        def can_finish(speed: int) -> bool:
            """
            Predikat Monotonik:
            Apakah Koko dapat menghabiskan seluruh pisang dalam <= h jam
            dengan kecepatan `speed`?
            """
            total_hours: int = 0
            for pile in piles:
                # Formula ceiling tanpa konversi float: (pile + speed - 1) // speed
                total_hours += (pile + speed - 1) // speed
                if total_hours > h:
                    return False
            return total_hours <= h

        # Ruang pencarian k: kecepatan minimum 1, kecepatan maksimum max(piles)
        left: int = 1
        right: int = max(piles)
        ans: int = right

        while left <= right:
            mid: int = left + (right - left) // 2
            
            if can_finish(mid):
                ans = mid       # mid valid, simpan dan coba cari kecepatan lebih rendah
                right = mid - 1
            else:
                left = mid + 1  # mid terlalu lambat, naikkan batas bawah kecepatan
                
        return ans
```

---

### 11. Real World Example
**Sistem Penyimpanan Terdistribusi: Pencarian Offset Log Apache Kafka**

File log segment Kafka (`.log`) menyimpan pesan secara berurutan. Kafka membuat sparse index (`.index`) yang memetakan `BaseOffset` ke `PhysicalPosition` di disk. 

Ketika consumer meminta pesan pada *target offset* tertentu:
1. Broker membaca memori buffer terpetakan (*memory-mapped file*) dari file `.index`.
2. Binary search dieksekusi pada entri indeks untuk menemukan physical file position terbesar yang offset-nya $\le$ target offset.
3. Setelah pointer physical didapatkan melalui binary search $O(\log M)$, sistem hanya perlu melakukan linear scan lokal kecil pada file `.log` fisik untuk membaca payload actual.

```
Request: Offset 1054
Index Array: [ [Offset 1000, Pos 0], [Offset 1050, Pos 4096], [Offset 1100, Pos 8192] ]
                      │                      ▲
                      │                      │
                      └──> Binary Search ────┘ (Hasil: Index 1050, Jump ke Pos 4096)
```

---

### 12. Trade-offs

| Pendekatan | Akses Memori | Kompleksitas Waktu (Pencarian) | Kompleksitas Ruang | Kebutuhan Pra-syarat |
| :--- | :--- | :--- | :--- | :--- |
| **Linear Search** | Sekuensial (Cache-friendly) | $O(N)$ | $O(1)$ | Tidak terurut |
| **Binary Search** | Random Jump (Banyak Cache Miss) | $O(\log N)$ | $O(1)$ | Harus terurut / Predikat monotonik |
| **Hash Table Lookup** | Random (Berdasarkan hash) | $O(1)$ amortized | $O(N)$ | Memory overhead besar, tidak mendukung range query |

---

### 13. When To Use
- Data berada dalam struktur array terurut dan frekuensi pencarian lebih dominan daripada modifikasi (*mutation*).
- Masalah memuat batasan nilai optimasi (*Minimize maximum...* atau *Maximize minimum...*).
- Menghitung frekuensi kemunculan rentang nilai $[A, B]$ dalam array terurut via `upper_bound(B) - lower_bound(A)`.

---

### 14. When NOT To Use
- Data tersimpan dalam *Singly Linked List*. Traversal menuju $mid$ memakan waktu $O(N)$, membuat kompleksitas total tetap $O(N)$ dengan beban cache locality yang buruk.
- Ukuran array sangat kecil ($N \le 16 \text{ hingga } 32$). *Instruction pipelining* dan SIMD linear scanning lebih cepat daripada *branch mispredictions* dari Binary Search.
- Ruang pencarian data tidak memiliki sifat predikat monotonik.

---

### 15. Common Mistakes
1. **Integer Overflow saat kalkulasi Midpoint:**
   ```c
   // BURUK (Bisa overflow jika left + right > INT_MAX)
   int mid = (left + right) / 2;
   
   // BAIK
   int mid = left + (right - left) / 2;
   ```
2. **Infinite Loop akibat update boundary yang salah:**
   Menggunakan template `while (left < right)` tetapi menetapkan `left = mid` saat kalkulasi pembulatan ke bawah (*round-down*), menyebabkan nilai `mid` tidak pernah bergeser saat selisih rentang tinggal 1.
3. **Mengabaikan validasi indeks di luar batas (Out of Bounds):**
   Memanggil `nums[left]` tanpa memvalidasi apakah `left == len(nums)` setelah loop terminasi.

---

### 16. Best Practices
- **Standardisasi Pola:** Gunakan pola interval inklusif $[L, R]$ secara konsisten.
  - Inisialisasi: `left = 0`, `right = len(nums) - 1`.
  - Terminasi: `while left <= right`.
  - Update: `left = mid + 1` dan `right = mid - 1`.
- **Fungsi Predikat Murni:** Pastikan fungsi predikat beroperasi secara deterministik dan bebas *side-effects*.
- **Pengecekan Tipe Batas:** Tentukan domain pencarian secara cermat pada problem *Binary Search on Answer* untuk memastikan nilai minimum dan maksimum valid secara absolut.

---

### 17. Troubleshooting

| Gejala Masalah | Akar Penyebab (*Root Cause*) | Solusi Korektif |
| :--- | :--- | :--- |
| *Infinite Loop* saat tersisa 2 elemen | `left = mid` digunakan bersamaan dengan `mid = left + (right - left) // 2` | Gunakan `mid = left + (right - left + 1) // 2` (bias ke kanan) atau standarisasi ke interval `left = mid + 1` |
| `IndexError: list index out of range` | Target lebih besar dari semua elemen array; pointer `left` meluncur ke `len(nums)` | Selalu validasi: `if left < len(nums) and nums[left] == target:` |
| Hasil salah pada array dengan duplikat | Logika percabangan `nums[mid] == target` langsung menghentikan proses | Arahkan pencarian ke kiri (`right = mid - 1`) untuk first occurrence, atau ke kanan (`left = mid + 1`) untuk last occurrence |

---

### 18. Exercise
**Instruksi:** Selesaikan permasalahan berikut secara mandiri tanpa menggunakan library biner bawaan (seperti `bisect`).

**Problem Statement:**
Diberikan array integer `nums` yang telah diurutkan secara menaik (ascending) dan memiliki nilai-nilai yang terduplikasi. Buatlah fungsi dengan efisiensi waktu $O(\log N)$ untuk mengembalikan rentang indeks awal dan akhir dari suatu `target`:
`search_range(nums: List[int], target: int) -> List[int]`
Jika `target` tidak ditemukan, kembalikan `[-1, -1]`.

---

### 19. Challenge
**Tantangan Tingkat Lanjut (Median of Two Sorted Arrays - LeetCode 4):**
Diberikan dua array terurut `nums1` dan `nums2` dengan ukuran masing-masing $M$ dan $N$. Tuliskan fungsi untuk menemukan median dari gabungan kedua array tersebut dengan kompleksitas waktu wajib **$O(\log(\min(M, N)))$**.

*Petunjuk Implementasi:* Lakukan partisi biner pada array yang berukuran lebih pendek, sedemikian rupa sehingga jumlah elemen di sebelah kiri partisi sama dengan jumlah elemen di sebelah kanan partisi, serta semua elemen di sisi kiri selalu $\le$ semua elemen di sisi kanan.

---

### 20. Summary
- Binary Search adalah paradigma eliminasi ruang pencarian berdasarkan predikat boolean yang terurut monotonik ($F \dots FT \dots T$).
- Terminasi loop yang deterministik didikte oleh konsistensi **Loop Invariant** dan update boundary yang selalu memotong ruang pencarian secara ketat.
- Pola *Binary Search on Answer* memperluas kegunaan algoritma ini melampaui array terurut statis, memungkinkan pencarian parameter optimal pada ruang solusi yang kompleks.