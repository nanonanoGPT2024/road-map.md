## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `CF-04-01`
* **Jalur Kurikulum**: *LeetCode & Competitive Programming Mastery*
* **Kategori**: `01-Core-Foundations`
* **Bab 04**: *Binary Search & Divide and Conquer*
* **Modul 01**: *Fundamental Binary Search, Loop Invariants, dan Paradigma Divide and Conquer*
* **Prasyarat**:
  * Pemahaman dasar struktur data Array dan manipulasi indeks ($O(1)$ *random access*).
  * Pemahaman Asimptotik Kompleksitas Waktu & Ruang (Notasi Big-O, Master Theorem dasar).
  * Pemahaman rekursi dasar dan terminasi rekursif.
* **Estimasi Durasi**: 180 Menit (Teori: 60 Menit, Bedah Kode & Visualisasi: 45 Menit, Praktik & Problem Solving: 75 Menit).
* **Target Tingkat Kemahiran**: Intermediate (*Lower Division Undergraduate CS* / *L4 Software Engineer Interview Readiness*).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membuktikan** kebenaran algoritma *Binary Search* menggunakan *Loop Invariant* formal pada interval tertutup `[left, right]` maupun setengah terbuka `[left, right)`.
2. **Mengidentifikasi dan Menerapkan** transformasi masalah dari pencarian nilai diskrit menjadi evaluasi fungsi predikat monotonik (*Binary Search on Answer Space / Feasibility Function*).
3. **Mengeliminasi** bug klasik implementasi seperti *arithmetic integer overflow*, *infinite loop*, dan *off-by-one errors* pada transisi batas (`left = mid + 1` vs `left = mid`).
4. **Mengkonstruksi** varian batas (*lower bound* / *bisect_left* dan *upper bound* / *bisect_right*) secara deterministik tanpa manipulasi heuristik yang rapuh.
5. **Menghubungkan** relasi formal rekurensi *Divide and Conquer* ($T(n) = aT(n/b) + f(n)$) dengan mekanisme reduksi ruang pencarian logaritmik ($T(n) = T(n/2) + O(1)$).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                    DIVIDE AND CONQUER PARADIGM
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       Multi-Branch Reduction           Single-Branch Reduction
       (e.g., Merge Sort,               (Prune and Search)
        Karatsuba, Strassen)                     │
                                                 ▼
                                        BINARY SEARCH CORE
                                                 │
        ┌────────────────────────────────────────┼────────────────────────────────────────┐
        ▼                                        ▼                                        ▼
Structural Invariants                   Monotonicity Property                   Search Space Topology
  ├── Closed: [L, R]                      ├── Sorted Array Values                 ├── Discrete Indices
  ├── Half-Open: [L, R)                   ├── Monotonic Predicate P(x)            ├── Continuous/Real Values
  └── Termination: L > R vs L == R        └── Transition Point (F -> T)           └── Solution Space P(k)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Secara historis, implementasi *Binary Search* yang bebas dari cacat logika terbukti sulit. Donald Knuth dalam bukunya *The Art of Computer Programming* mencatat bahwa meskipun algoritma ini dipublikasikan pertama kali pada 1946, implementasi pertama yang sepenuhnya benar tanpa bug baru diterbitkan pada tahun 1962. Pada tahun 2006, Joshua Bloch menemukan bug *integer overflow* (`(low + high) / 2`) di pustaka standar Java (`java.util.Arrays`) yang telah bersembunyi selama hampir satu dekade.

```
Ukuran Input (n)      Linear Search O(n)       Binary Search O(log2 n)    Rasio Efisiensi
─────────────────────────────────────────────────────────────────────────────────────────
1,000                 1,000 operasi            ~10 operasi                100x
1,000,000             1,000,000 operasi        ~20 operasi                50,000x
1,000,000,000         1,000,000,000 operasi    ~30 operasi                33,333,333x
```

Dalam wawancara teknis tingkat lanjut (*FAANG / Tier-1 Tech*), *Binary Search* jarang diuji hanya sebatas mencari indeks angka pada array terurut. Ia diuji sebagai teknik optimasi untuk memecahkan masalah berskala $O(N)$ atau $O(N^2)$ menjadi $O(\log(\text{range}) \times \text{evaluasi})$, menjadikannya salah satu alat reduksi kompleksitas paling fundamental dalam sains komputasi.

---

## SEKSI 05 — APA ITU (WHAT)

### Definisi Matematis
Secara umum, *Binary Search* adalah algoritma reduksi ruang pencarian (*search space reduction*) berbasis eliminasi separuh kandidat secara deterministik pada setiap langkah. Diberikan domain terurut atau terpartisi $\mathcal{S}$ dan sebuah fungsi predikat boolean monotonik:

$$P: \mathcal{S} \to \{0, 1\} \quad \text{atau} \quad P: \mathcal{S} \to \{\text{False}, \text{True}\}$$

Monotonisitas mensyaratkan bahwa jika $x \le y$, maka berlaku salah satu kondisi berikut secara global:
1. **Monoton Naik**: $P(x) \implies P(y)$ (Rentang bernilai: `[False, False, ..., True, True]`)
2. **Monoton Turun**: $\neg P(x) \implies \neg P(y)$ (Rentang bernilai: `[True, True, ..., False, False]`)

Tujuan dari *Binary Search* adalah menemukan elemen batas $x^*$ sedemikian rupa sehingga:

$$x^* = \min \{ x \in \mathcal{S} \mid P(x) = \text{True} \}$$

### Relasi dengan Divide and Conquer
*Divide and Conquer* (D&C) memiliki 3 pilar:
1. **Divide**: Membagi masalah menjadi sub-masalah yang lebih kecil.
2. **Conquer**: Menyelesaikan sub-masalah secara rekursif (atau langsung jika mencapai *base case*).
3. **Combine**: Menggabungkan solusi sub-masalah menjadi solusi utuh.

*Binary Search* adalah bentuk khusus D&C yang disebut **Prune-and-Search** (atau *Degenerate Divide and Conquer*):
* Masalah dibagi menjadi dua sub-masalah berukuran $n/2$.
* Bagian **Combine** berbiaya $O(0)$ (tidak ada operasi penggabungan) karena pembuktian predikat membuang (*prunes*) separuh domain secara permanen.
* Solusi terletak murni pada satu cabang penelusuran.
* Berdasarkan Master Theorem: $T(n) = aT(n/b) + f(n)$ dengan $a = 1, b = 2, f(n) = O(1)$, menghasilkan $T(n) = \Theta(\log n)$.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Implementasi yang benar menuntut kepatuhan mutlak pada satu set *invariants*. Dua template utama yang paling stabil secara matematis adalah:
1. **Template Interval Tertutup**: Ruang kandidat adalah $[L, R]$.
2. **Template Interval Predikat Monotonik**: Mencari batas transisi pertama bernilai `True`.

### 1. Perhitungan Titik Tengah (*Midpoint Calculation*)
Penggunaan ekspresi standar:
$$\text{mid} = \lfloor \frac{L + R}{2} \rfloor$$
Rawan terhadap *integer overflow* dalam bahasa bertipe statis (C, C++, Java, Rust, Go) ketika $L + R > 2^{31}-1$.
Formulasi yang aman secara numerik adalah:

$$\text{mid} = L + \lfloor \frac{R - L}{2} \rfloor$$

Untuk pembagian bulat ke atas (*ceil* / bias kanan):
$$\text{mid} = L + \lfloor \frac{R - L + 1}{2} \rfloor$$

### 2. Invarian Loop pada Interval Tertutup $[L, R]$
* **Kondisi Loop**: `while L <= R:`
* **Arti Ruang**: $L$ dan $R$ keduanya merupakan indeks yang masih valid sebagai kandidat solusi.
* **Kondisi Terminasi**: Loop berakhir ketika $L = R + 1$. Ruang pencarian menjadi $[R+1, R]$ (interval kosong), membuktikan bahwa target tidak ditemukan dalam domain.
* **Pembaruan Interval**:
  * Jika target berada di sebelah kiri `mid`: $R = \text{mid} - 1$
  * Jika target berada di sebelah kanan `mid`: $L = \text{mid} + 1$

### 3. Invarian Transisi Predikat (*Lower Bound / First True*)
* **Kondisi Loop**: `while L < R:`
* **Arti Ruang**: Solusi optimal selalu berada di dalam interval tertutup $[L, R]$.
* **Pembaruan Batas**:
  * Jika $P(\text{mid}) == \text{True}$: Solusi mungkin adalah `mid`, atau berada di sebelah kirinya. Maka batas kanan dipersempit tanpa membuang `mid`: $R = \text{mid}$.
  * Jika $P(\text{mid}) == \text{False}$: Solusi pasti bukan `mid`, melainkan berada di kanannya: $L = \text{mid} + 1$.
* **Terminasi**: Loop berhenti persis saat $L == R$. Titik temu tersebut adalah solusi akhir tanpa perlu pengecekan ulang di luar loop.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Visualisasi Reduksi Search Space pada Predikat Monotonik

Diberikan array yang telah dipetakan terhadap predikat $P(x) \iff \text{array}[x] \ge 35$:

```
Indeks (i):    0      1      2      3      4      5      6      7
Array [i]:    10     14     22     33     35     42     50     88
P(Array[i]): False  False  False  False   True   True   True   True
Target: Menemukan indeks terkecil i di mana P(i) == True (yaitu indeks 4)

───────────────────────────────────────────────────────────────────────────
ITERASI 1:
L = 0, R = 7
mid = 0 + (7 - 0) // 2 = 3

Indeks:       0      1      2      3      4      5      6      7
Elemen:      10     14     22    [33]    35     42     50     88
Kandidat:    [L                    mid                         R]
P(mid) = False -> Array[3] < 35. 
Keputusan: Solusi berada di kanan mid. Set L = mid + 1 (4).
Pruned: [0, 1, 2, 3] dieliminasi.

───────────────────────────────────────────────────────────────────────────
ITERASI 2:
L = 4, R = 7
mid = 4 + (7 - 4) // 2 = 5

Indeks:       0      1      2      3      4      5      6      7
Elemen:       x      x      x      x     35    [42]    50     88
Kandidat:                                [L     mid            R]
P(mid) = True -> Array[5] >= 35.
Keputusan: mid bisa jadi solusi minimum, atau ada di kirinya. Set R = mid (5).
Pruned: [6, 7] dieliminasi.

───────────────────────────────────────────────────────────────────────────
ITERASI 3:
L = 4, R = 5
mid = 4 + (5 - 4) // 2 = 4

Indeks:       0      1      2      3      4      5      6      7
Elemen:       x      x      x      x    [35]    42      x      x
Kandidat:                                [L/mid  R]
P(mid) = True -> Array[4] >= 35.
Keputusan: Set R = mid (4).

───────────────────────────────────────────────────────────────────────────
TERMINASI:
L = 4, R = 4 (Kondisi L == R terpenuhi)
Loop Berakhir. Solusi mutlak berada pada indeks L = 4 (Nilai: 35).
Jumlah Operasi Reduksi: 3 langkah (log2(8) = 3).
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi kanonikal pencarian nilai eksak (*Exact Value Search*) dan pencarian batas kiri (*Lower Bound / Bisect Left*) menggunakan Python 3.

```python
from typing import List

def binary_search_exact(nums: List[int], target: int) -> int:
    """
    Mencari indeks target pada array terurut menaik nums.
    Mengembalikan -1 jika target tidak ditemukan.
    Kompleksitas Waktu: O(log n)
    Kompleksitas Ruang: O(1)
    """
    left: int = 0
    right: int = len(nums) - 1  # Invarian: ruang pencarian [left, right]

    while left <= right:
        # Menghindari integer overflow pada bahasa bertipe statis
        mid: int = left + (right - left) // 2
        
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            left = mid + 1       # Target berada di separuh kanan
        else:
            right = mid - 1      # Target berada di separuh kiri

    return -1                    # Ruang pencarian kosong, target tidak ada


def lower_bound(nums: List[int], target: int) -> int:
    """
    Mencari indeks pertama i sedemikian rupa sehingga nums[i] >= target.
    Jika semua elemen < target, mengembalikan len(nums).
    Karakteristik: P(x) = nums[x] >= target (Monoton Naik: False -> True)
    """
    left: int = 0
    right: int = len(nums)      # Menggunakan interval setengah terbuka [0, n]

    while left < right:
        mid: int = left + (right - left) // 2
        if nums[mid] >= target:
            right = mid         # mid memenuhi predikat, persempit ke kiri
        else:
            left = mid + 1      # mid tidak memenuhi predikat, eliminasi mid

    return left                 # Pada akhir loop, left == right
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Studi Kasus: *Capacity To Ship Packages Within D Days* (LeetCode 1011)

**Deskripsi Masalah**:
Diberikan array `weights` berisi bobot paket yang harus dikirim secara berurutan, dan bilangan bulat `days`. Kita harus menentukan kapasitas muatan kapal minimum sehingga seluruh paket dapat terkirim dalam waktu paling banyak `days` hari. Kapal tidak boleh dimuat melebihi kapasitas maksimumnya per hari.

**Analisis Reduksi Ruang Pencarian**:
* Ruang Jawaban (*Search Space*): Berapa kapasitas minimum yang mungkin?
  * Batas bawah ($L$): $\max(\text{weights})$ — Kapal harus bisa memuat paket terberat.
  * Batas atas ($R$): $\sum \text{weights}$ — Kapal mengangkut semua paket dalam 1 hari.
* Monotonisitas: Jika kapasitas $C$ sanggup menyelesaikan pengiriman dalam $\le \text{days}$, maka setiap kapasitas $C' > C$ pasti sanggup. Ini adalah fungsi predikat $P(C) \to \{\text{False}, \dots, \text{False}, \text{True}, \dots, \text{True}\}$.

```python
from typing import List

class Solution:
    def shipWithinDays(self, weights: List[int], days: int) -> int:
        """
        Menentukan kapasitas minimum kapal untuk mengirim paket dalam 'days' hari.
        
        Kompleksitas Waktu: O(N * log(Sum(weights) - Max(weights)))
        Kompleksitas Ruang: O(1)
        """
        def can_ship_with_capacity(capacity: int) -> bool:
            """Fungsi predikat monotonik: Mengembalikan True jika kapasitas valid."""
            current_day_load = 0
            required_days = 1
            
            for w in weights:
                if current_day_load + w > capacity:
                    required_days += 1
                    current_day_load = w
                else:
                    current_day_load += w
            
            return required_days <= days

        # Inisialisasi batas bawah dan atas search space
        left: int = max(weights)
        right: int = sum(weights)

        # Template Lower Bound: Mencari kapasitas terkecil yang menghasilkan True
        while left < right:
            mid: int = left + (right - left) // 2
            
            if can_ship_with_capacity(mid):
                # Kapasitas ini mencukupi; cari apakah ada kapasitas lebih kecil di kiri
                right = mid
            else:
                # Kapasitas tidak mencukupi; kapasitas harus lebih besar dari mid
                left = mid + 1

        return left
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan Algoritmik | Kompleksitas Waktu | Kompleksitas Ruang | Prasyarat Struktur | Kelebihan | Kelemahan |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Linear Search** | $O(N)$ | $O(1)$ | Tidak ada (dapat acak) | Simpel, performa cache CPU optimal pada array kecil | Tidak *scale* pada data masif ($N > 10^5$) |
| **Binary Search** | $O(\log N)$ | $O(1)$ | Random Access $O(1)$ + Monotonisitas | Sangat cepat secara asimptotik | Membutuhkan struktur data terurut dan *contiguous memory* |
| **Hash Set / Map Lookup** | Rata-rata $O(1)$, Terburuk $O(N)$ | $O(N)$ | Elemen harus *hashable* | Pencarian instan untuk titik tunggal | Overhead memori tinggi, tidak mendukung *range queries* |
| **Balanced BST (e.g., AVL, Red-Black)** | $O(\log N)$ | $O(N)$ | Pointer overhead | Fleksibel untuk operasi dinamis (*insert/delete*) | *Poor cache locality* dibanding array contiguous |

### Pertimbangan Pola Akses Memori (*Hardware Cache*)
Pada arsitektur komputer modern, *Binary Search* pada rentang data besar ($> 10^7$ elemen) memicu *cache miss* pada hampir setiap perbandingan di iterasi awal, karena melompat melintasi blok memori yang jauh. Untuk array berukuran sangat kecil ($N \le 64$), *Linear Search* tervektorisasi (SIMD) sering kali lebih cepat daripada *Binary Search* karena efisiensi *CPU prefetching* dan tidak adanya *branch misprediction*.

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Integer Arithmetic Guard Secara Konsisten**: Selalu gunakan `mid = left + (right - left) // 2` alih-alih `(left + right) // 2`.
2. **Definisikan Makna Invarian Secara Eksplisit Sebelum Menulis Kode**:
   * Jika menggunakan `left <= right`: Anda mengecek nilai diskrit. Pembaruan harus selalu mengecualikan `mid`: `left = mid + 1` dan `right = mid - 1`.
   * Jika menggunakan `left < right`: Anda mencari titik batas (*boundary*). Pembaruan harus mempertahankan kandidat: `right = mid` dan `left = mid + 1` (atau sebaliknya untuk bias kanan).
3. **Cegah Infinite Loop pada Bias Integer**:
   * Ketika memperbarui `left = mid` dengan formula `mid = left + (right - left) // 2`, jika selisih `right - left == 1`, maka `mid` akan terhitung sama dengan `left`. Ini menyebabkan loop tak terbatas (*infinite loop*). Solusi: Ubah pembagian menjadi bias kanan: `mid = left + (right - left + 1) // 2`.
4. **Isolasi Logika Predikat**: Ekstraksi kondisi validasi menjadi fungsi terpisah (misalnya `is_possible()`, `check()`, `is_valid()`) untuk memisahkan domain verifikasi kompleks dari kontrol alur biner.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Arithmetic Overflow
* **Kode Salah**:
  ```cpp
  int mid = (left + right) / 2; // UB / Overflow jika left + right > INT_MAX
  ```
* **Koreksi**:
  ```cpp
  int mid = left + (right - left) / 2;
  ```

### 2. Off-by-One dan Loop Hang (Stall)
* **Kondisi Rusak**:
  ```python
  # KASUS: Mencari elemen maksimum yang valid
  while left < right:
      mid = left + (right - left) // 2 # Bias kiri
      if check(mid):
          left = mid # BUG: Jika left = 3, right = 4 -> mid = 3 -> left = 3 (STUCK FOREVER)
      else:
          right = mid - 1
  ```
* **Koreksi**:
  ```python
  while left < right:
      mid = left + (right - left + 1) // 2 # Bias kanan menyelesaikan masalah
      if check(mid):
          left = mid
      else:
          right = mid - 1
  ```

### 3. Asumsi Terurut pada Data yang Tidak Monotonik
Menerapkan *Binary Search* langsung pada array yang memiliki duplikasi tanpa analisis rotasi yang memadai (misalnya *Search in Rotated Sorted Array II* dengan elemen duplikat di mana $A[L] == A[\text{mid}] == A[R]$, yang menurunkan kompleksitas menjadi terburuk $O(N)$).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: *Easy* — Implementasi Lower Bound Standar
* **Problem**: Diberikan array bilangan bulat `nums` yang diurutkan secara menaik dan sebuah nilai `target`, kembalikan indeks kemunculan pertama `target`. Jika tidak ditemukan, kembalikan indeks di mana `target` seharusnya disisipkan agar urutan tetap terjaga (identik dengan `bisect_left`).
* **Batasan**: $N \le 10^5$, $-10^9 \le \text{nums}[i] \le 10^9$. Waktu harus $O(\log N)$, Ruang $O(1)$.
* **Petunjuk**: Gunakan template `left < right` dengan invarian $P(x) \iff \text{nums}[x] \ge \text{target}$.

### Latihan 2: *Medium* — Koko Eating Bananas (LeetCode 875)
* **Problem**: Ada $N$ tumpukan pisang, tumpukan ke-$i$ berisi `piles[i]` pisang. Penjaga pergi selama $H$ jam. Koko dapat memutuskan kecepatan makan $K$ pisang per jam. Temukan nilai integer minimum $K$ sehingga dia dapat memakan semua pisang dalam batas waktu $H$ jam.
* **Batasan**: $1 \le \text{len}(piles) \le 10^4$, $\text{len}(piles) \le H \le 10^9$, $1 \le \text{piles}[i] \le 10^9$.
* **Petunjuk**: Tentukan *search space* untuk $K$. Evaluasi apakah durasi $\lceil \text{piles}[i] / K \rceil$ monoton terhadap perubahan $K$.

### Latihan 3: *Hard* — Median of Two Sorted Arrays (LeetCode 4)
* **Problem**: Diberikan dua array terurut `nums1` dan `nums2` dengan ukuran masing-masing $m$ dan $n$. Temukan median dari gabungan kedua array tersebut dalam kompleksitas waktu $O(\log(\min(m, n)))$.
* **Batasan**: $0 \le m \le 1000$, $0 \le n \le 1000$, $m + n \ge 1$.
* **Petunjuk**: Partisi kedua array menjadi dua bagian (kiri dan kanan) yang seimbang. Terapkan *Binary Search* hanya pada array yang berukuran lebih kecil untuk menemukan titik partisi horizontal yang valid.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Pertanyaan**: Mengapa interval setengah terbuka `[0, n)` sering dipilih untuk algoritma partisi seperti *lower bound* alih-alih `[0, n - 1]`?
   * *Jawaban Model*: Karena jika seluruh elemen dalam array bernilai lebih kecil dari `target`, indeks penyisipan yang valid berada di luar batas array, yaitu indeks $n$. Rentang `[0, n]` memungkinkan representasi status "tidak ditemukan/sisipkan di akhir" secara alamiah.

2. **Pertanyaan**: Diberikan perulangan:
   ```python
   while left < right:
       mid = left + (right - left) // 2
       if predicate(mid):
           right = mid
       else:
           left = mid + 1
   ```
   Apakah perulangan di atas dapat mengalami *infinite loop* ketika `right - left == 1`? Jelaskan!
   * *Jawaban Model*: Tidak. Ketika `right - left == 1`, maka `mid = left + 0 = left`. Jika `predicate(mid)` bernilai `True`, `right` menjadi `left`, sehingga loop terminasi (`left == right`). Jika `False`, `left` menjadi `mid + 1` (yang mana adalah `right`), loop juga terminasi.

3. **Tracing Kasus Uji**:
   * Array: `[2, 4, 6, 8, 10]`, Target: `7`.
   * Tuliskan urutan `(left, mid, right)` hingga terminasi menggunakan fungsi `binary_search_exact`.
   * *Jawaban Model*:
     * Inisialisasi: $L=0, R=4$
     * Langkah 1: $\text{mid} = 2 \implies \text{nums}[2] = 6 < 7 \implies L = 3$
     * Langkah 2: $L=3, R=4 \implies \text{mid} = 3 \implies \text{nums}[3] = 8 > 7 \implies R = 2$
     * Evaluasi Loop: $L = 3, R = 2 \implies L > R$ (Terminasi). Return -1.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Teks Utama**:
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.). MIT Press. (Bab 2: Getting Started - Divide and Conquer, Bab 28: Master Theorem).
  * Knuth, D. E. (1998). *The Art of Computer Programming, Volume 3: Sorting and Searching* (2nd ed.). Addison-Wesley. (Seksi 6.2.1: Searching an Ordered Table).
* **Makalah & Dokumentasi Historis**:
  * Bloch, J. (2006). *Extra, Extra - Read All About It: Nearly All Binary Searches and Mergesorts are Broken*. Google Research Blog.
* **LeetCode Curated List**:
  * Topik: *Binary Search*, *Binary Search on Answer*. Soal-soal: LC 704, LC 35, LC 34, LC 162, LC 153, LC 875, LC 1011, LC 410, LC 4.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 BINARY SEARCH CHEAT SHEET                              │
├──────────────────────┬────────────────────────────────┬────────────────────────────────┤
│ Pola Invarian        │ Interval Tertutup [L, R]       │ Interval Terbuka Kanan [L, R)  │
├──────────────────────┼────────────────────────────────┼────────────────────────────────┤
│ Inisialisasi         │ L = 0, R = n - 1               │ L = 0, R = n                   │
│ Kondisi Perulangan   │ while L <= R                   │ while L < R                    │
│ Titik Tengah         │ mid = L + (R - L) // 2         │ mid = L + (R - L) // 2         │
│ Kondisi Sukses Cepat │ if nums[mid] == target: return │ Tidak ada (converge ke bound)  │
│ Arah Kiri            │ R = mid - 1                    │ R = mid                        │
│ Arah Kanan           │ L = mid + 1                    │ L = mid + 1                    │
│ Kondisi Pasca-Loop   │ Target tidak ada (L > R)       │ L == R (Titik Transisi)        │
└──────────────────────┴────────────────────────────────┴────────────────────────────────┘
```

Kunci keberhasilan implementasi *Binary Search* terletak pada perumusan fungsi predikat boolean $P(x)$ yang menjamin eksistensi pola monotonik. Setelah pola tersebut terbentuk, pencarian solusi optimal setara dengan menemukan indeks pertama bernilai `True`.

---

## SEKSI 17 — GLOSARIUM

* **Bias Kiri / Kanan (*Rounding Bias*)**: Kecenderungan pembulatan pada pembagian integer. Integer division membulatkan ke bawah (bias kiri). Bias kanan diperoleh dengan menambahkan 1 sebelum pembagian.
* **Divide and Conquer**: Paradigma perancangan algoritma yang memecah masalah menjadi sub-masalah independen, menyelesaikannya secara terpisah, lalu menggabungkan hasilnya.
* **Fungsi Predikat (*Predicate Function*)**: Fungsi matematis $P: X \to \{0, 1\}$ yang memetakan elemen input ke dalam status benar (*True*) atau salah (*False*).
* **Loop Invariant**: Proposisi logis yang bernilai benar sebelum dan sesudah setiap iterasi dari suatu perulangan berjalan, digunakan untuk membuktikan kebenaran algoritma secara formal.
* **Lower Bound**: Indeks elemen pertama dalam rentang terurut yang nilainya tidak kurang dari (*greater than or equal to*) target yang ditentukan.
* **Monotonisitas (*Monotonicity*)**: Sifat fungsi di mana urutan nilainya tidak pernah berubah arah (selalu tidak turun atau selalu tidak naik) di sepanjang domainnya.
* **Prune and Search**: Varian algoritma di mana ukuran input diperkecil dengan faktor konstan pada setiap iterasi tanpa perlu menggabungkan sub-solusi dari beberapa cabang.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Krusial Pedagogis**:
  * Jangan biarkan peserta didik menghafal template tanpa memahami arti batas `[L, R]`. Tekankan selalu pertanyaan: *"Apakah `mid` masih memiliki kemungkinan menjadi jawaban?"* Jika YA $\implies R = \text{mid}$ atau $L = \text{mid}$. Jika TIDAK $\implies R = \text{mid} - 1$ atau $L = \text{mid} + 1$.
  * Tunjukkan secara langsung kepada peserta didik kegagalan loop menggunakan *tracing live* pada array dua elemen `[2, 5]` dengan formula bias yang salah untuk menunjukkan *infinite loop*.
* **Penyampaian Materi Feasibility Function**:
  * Tekankan bahwa predikat $P(x)$ bertindak seperti sakelar listrik: tugas peserta bukan lagi mencari angka di array, melainkan mencari batas kabel yang putus (transisi `0` ke `1`). Hal ini mengubah pola pikir dari "pencarian array" menjadi "optimasi fungsi".

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Tanggal: 2026-03-30)
  * Rilis modul perdana kurikulum Core Foundations: Bab 04 - Modul 01.
  * Penyusunan analisis matematis Master Theorem, eliminasi arithmetic overflow, visualisasi ASCII diagram, dan integrasi studi kasus *Capacity To Ship Packages Within D Days*.
  * Penulis: *Senior Technical Curriculum Architect (Core Engineering Team)*.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CF-03-03` — *Sliding Window Dynamic vs Fixed Size & Two Pointers Advanced Patterns*
* **Modul Saat Ini**: `CF-04-01` — *Fundamental Binary Search, Loop Invariants, dan Paradigma Divide and Conquer*
* **Modul Berikutnya**: `CF-04-02` — *Binary Search on Answer Space, Rotated Arrays, & Real-Number Domains*