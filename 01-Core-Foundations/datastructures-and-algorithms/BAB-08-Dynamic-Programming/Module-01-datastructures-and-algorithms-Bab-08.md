## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: DSA-01-08-001
* **Nama Modul**: Dynamic Programming Fundamentals: Optimal Substructure, Memoization, dan Tabulation
* **Kategori**: 01-Core-Foundations
* **Jalur Pembelajaran**: Data Structures & Algorithms Core Track
* **Prasyarat**:
  * DSA-01-04-001 (Recursion & Divide-and-Conquer)
  * DSA-01-02-001 (Asymptotic Complexity & Big-O Notation)
  * DSA-01-05-001 (Linear Data Structures: Arrays & Hash Maps)
* **Tingkat Kesulitan**: Intermediate to Advanced
* **Estimasi Waktu Baca**: 45 menit
* **Estimasi Waktu Praktik**: 90 menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membuktikan Karakteristik Masalah DP**: Mengidentifikasi apakah suatu masalah komputasi memiliki dua properti fundamental: *Optimal Substructure* dan *Overlapping Subproblems*.
2. **Merumuskan Relasi Rekurens (*Recurrence Relation*)**: Menyusun formulasi matematis untuk transisi status (*state transition equation*) secara formal beserta *base cases*.
3. **Mengimplementasikan Pendekatan Top-Down (Memoization)**: Mentransformasikan algoritma rekursif eksponensial menjadi polinomial menggunakan teknik *caching* status rekursif.
4. **Mengimplementasikan Pendekatan Bottom-Up (Tabulation)**: Membangun solusi iteratif berbasis tabel dengan menentukan topologi dependensi status secara benar.
5. **Melakukan Optimasi Ruang (*Space Complexity Optimization*)**: Mereduksi dimensi tabel DP (misalnya dari $O(N)$ ke $O(1)$, atau $O(N \times W)$ ke $O(W)$) menggunakan teknik *rolling array* atau variabel penampung status.
6. **Membedakan Paradigma Algoritma**: Mengartikulasikan perbedaan fundamental antara *Dynamic Programming*, *Divide and Conquer*, dan *Greedy Approach*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              DYNAMIC PROGRAMMING (DP)
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
[2 Syarat Fundamental]                                            [Paradigma Solusi]
  ├── 1. Optimal Substructure                                       ├── 1. Top-Down (Memoization)
  │      (Solusi global optimal dibentuk                                │   ├── Rekursif murni
  │       dari solusi submasalah optimal)                              │   ├── Cache lookup / Table memo
  └── 2. Overlapping Subproblems                                        │   └── Call-stack overhead
         (Submasalah yang sama dieksekusi                               └── 2. Bottom-Up (Tabulation)
          berulang kali pada pohon rekursi)                                 ├── Iteratif
                                                                            ├── Topological ordering
                                                                            └── Ramah CPU Cache
                                         │
                                         ▼
                             [Proses Formulasi DP]
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
  [State Definition]           [State Transition]               [Space Optimization]
   Mendefinisikan parameter     Menentukan relasi rekurens:      Mereduksi alokasi memori
   unik yang merepresentasikan  DP[i] = f(DP[i-1], DP[i-2], ...) memanfaatkan dependensi
   submasalah spesifik                                           status paling mutakhir
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Algoritma rekursif naif sering kali memiliki kompleksitas waktu eksponensial seperti $O(2^N)$ atau $O(N!)$ karena melakukan kalkulasi ulang terhadap submasalah yang identik jutaan hingga miliaran kali. Sebagai contoh, menghitung deret Fibonacci ke-50 secara rekursif naif membutuhkan sekitar $2^{50} \approx 1.12 \times 10^{15}$ operasi komputasi. Pada prosesor standar (1 GHz clock rate), komputasi ini membutuhkan waktu lebih dari 13 hari. 

Dengan menerapkan *Dynamic Programming*, kalkulasi redundan dieliminasi dengan menyimpan hasil komputasi submasalah sebelumnya. Kompleksitas waktu Fibonacci tereduksi secara drastis dari $O(2^N)$ menjadi $O(N)$, menyelesaikan perhitungan $N=50$ dalam hitungan mikrodetik.

Dalam rekayasa perangkat lunak modern, DP bukan sekadar trik wawancara teknis. Prinsip DP menjadi fondasi dari:
* **Algoritma Perutean Jaringan**: Algoritma Bellman-Ford dan Floyd-Warshall untuk mencari jalur terpendek dalam graf berarah.
* **Bioinformatika**: Algoritma Needleman-Wunsch dan Smith-Waterman untuk *sequence alignment* DNA/RNA.
* **Natural Language Processing (NLP)**: Algoritma Viterbi pada Hidden Markov Models (HMM) untuk speech recognition dan part-of-speech tagging.
* **Sistem Kontrol & Riset Operasi**: *Resource allocation*, *portfolio management*, dan *knapsack-based scheduling engine*.
* **Tools Pengembangan Software**: Algoritma pencarian selisih teks (*diff engine*) seperti `git diff` yang berbasis algoritma *Longest Common Subsequence* (LCS).

---

## SEKSI 05 — APA ITU (WHAT)

Istilah *Dynamic Programming* pertama kali diperkenalkan oleh matematikawan Richard Bellman pada tahun 1950-an. Kata *"programming"* di sini tidak merujuk pada penulisan kode komputer, melainkan pada perencanaan matematis atau tabulasi (*tabular method*).

Secara formal, **Dynamic Programming (DP)** adalah paradigma desain algoritma yang memecahkan masalah optimasi atau pencarian dengan cara menguraikannya menjadi kumpulan submasalah yang saling tumpang tindih (*overlapping subproblems*), menyelesaikan masing-masing submasalah tersebut hanya satu kali, dan menyimpan solusinya ke dalam struktur data berbasis memori (tabel/array/hash map) untuk digunakan kembali saat submasalah yang sama muncul kemudian.

### Karakteristik Wajib

1. **Optimal Substructure**: Solusi optimal terhadap suatu masalah dapat dibangun secara langsung dari solusi optimal sub-submasalahnya.
   $$\text{Contoh: Jarak terpendek } A \to C \text{ melalui } B \text{ adalah } \text{dist}(A, C) = \text{dist}(A, B) + \text{dist}(B, C)$$
2. **Overlapping Subproblems**: Ruang submasalah haruslah kecil, dalam arti algoritma rekursif mengunjungi submasalah yang sama berulang kali, bukan selalu menghasilkan submasalah baru.

### Perbandingan Paradigma Algoritma

| Aspek | Dynamic Programming | Divide & Conquer | Greedy Approach |
| :--- | :--- | :--- | :--- |
| **Sifat Submasalah** | *Overlapping* (saling tumpang tindih) | *Independent* (independen) | *Subproblems* tidak dievaluasi serentak |
| **Pengambilan Keputusan** | Mengevaluasi semua transisi untuk memilih yang optimal | Memecah, menyelesaikan pecahan, menggabungkan | Memilih opsi terbaik lokal secara serakah di tiap langkah |
| **Kompleksitas Memori** | Seringkali membutuhkan $O(N)$ hingga $O(N^2)$ untuk tabel | $O(\log N)$ hingga $O(N)$ untuk call stack | Biasanya $O(1)$ |
| **Optimalitas Global** | Dijamin optimal jika perumusan benar | Dijamin optimal jika penggabungan benar | Tidak selalu menghasilkan optimal global |

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Untuk memecahkan masalah komputasi menggunakan Dynamic Programming, terdapat metodologi sistematis 5 langkah (*5-Step DP Framework*):

### Langkah 1: Definisi Status (*State Definition*)
Tentukan secara presisi apa arti dari status `DP[i]` atau `DP[i][j]`. Status harus memuat informasi minimum yang cukup untuk membuat keputusan ke langkah berikutnya tanpa ambigu.
* *Contoh*: `DP[i]` merepresentasikan nilai keuntungan maksimum yang dapat dicapai dari indeks barang `0` hingga `i`.

### Langkah 2: Identifikasi Base Case
Tentukan nilai paling dasar di mana komputasi trivial dapat langsung dijawab tanpa perlu rekursi lebih lanjut.
* *Contoh*: `DP[0] = 0` atau `DP[0] = 1`.

### Langkah 3: Rumuskan Relasi Rekurens (*State Transition Equation*)
Tuliskan hubungan logis dan matematis yang menghubungkan status saat ini (`DP[i]`) dengan satu atau beberapa status sebelumnya yang sudah terhitung (`DP[i-1]`, `DP[i-2]`, dll).
* *Contoh*: 
  $$\text{DP}[i] = \min(\text{DP}[i - 1], \text{DP}[i - 2]) + \text{cost}[i]$$

### Langkah 4: Tentukan Arah Komputasi (*Order of Computation*)
* **Top-Down (Memoization)**: Mulai dari masalah target akhir ($N$) menuju base case ($0$), simpan hasil ke tabel saat rekursi kembali (*unwinding*).
* **Bottom-Up (Tabulation)**: Mulai iterasi dari base case ($0$) secara linier menuju target akhir ($N$). Urutan komputasi harus menjamin bahwa status dependen sudah terisi sebelum diakses.

### Langkah 5: Optimasi Ruang (*State Space Reduction*)
Periksa relasi rekurens: jika `DP[i]` hanya membutuhkan `DP[i-1]` dan `DP[i-2]`, simpan nilai-nilai tersebut dalam 2 variabel terpisah tanpa mengalokasikan array sepanjang $N$.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah visualisasi pohon rekursi naif vs DAG (*Directed Acyclic Graph*) pada perhitungan Fibonacci $N=5$.

### Pohon Rekursi Naif (Menyebabkan Evaluasi Redundan)

```
                                  fib(5)
                       ┌────────────┴────────────┐
                     fib(4)                    fib(3)  <-- Duplikasi level 1
                 ┌─────┴─────┐              ┌─────┴─────┐
              fib(3)       fib(2)        fib(2)       fib(1)
            ┌───┴───┐     ┌──┴──┐       ┌──┴──┐
         fib(2)  fib(1) fib(1) fib(0) fib(1) fib(0)
         ┌──┴──┐
      fib(1) fib(0)

Total node: 15 pemanggilan rekursif. fib(3) dihitung 2x, fib(2) dihitung 3x.
Untuk N besar, pertumbuhan node adalah O(2^N).
```

### Transformasi Menjadi Directed Acyclic Graph (DAG) via DP

Dengan memoization atau tabulation, setiap submasalah direduksi menjadi satu simpul unik:

```
    [fib(0)] ───► [fib(1)] ───► [fib(2)] ───► [fib(3)] ───► [fib(4)] ───► [fib(5)]
       │             │             ▲             ▲             ▲             ▲
       │             └─────────────┴──────┬──────┘             │             │
       └──────────────────────────────────┘                    │             │
                                  │                            │             │
                                  └────────────────────────────┴──────┬──────┘
                                                                      │
                                                                      ▼
                                                                Target Akhir
Total operasi: Tepat N langkah (O(N) time complexity).
```

### Alur Eksekusi Tabulation (Bottom-Up)

```
Inisialisasi Array: dp = [0, 0, 0, 0, 0, 0] (ukuran N + 1)

Langkah 0: dp[0] = 0  (Base Case)
Langkah 1: dp[1] = 1  (Base Case)
Langkah 2: dp[2] = dp[1] + dp[0] = 1 + 0 = 1
Langkah 3: dp[3] = dp[2] + dp[1] = 1 + 1 = 2
Langkah 4: dp[4] = dp[3] + dp[2] = 2 + 1 = 3
Langkah 5: dp[5] = dp[4] + dp[3] = 3 + 2 = 5

Status Memori Akhir:
Index:   0    1    2    3    4    5
Array: [ 0 ][ 1 ][ 1 ][ 2 ][ 3 ][ 5 ]
                                   ▲
                                   └── Hasil Akhir Dikembalikan
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Masalah: **Climbing Stairs**
Ada tangga dengan $N$ anak tangga. Anda dapat melangkah 1 atau 2 langkah sekaligus. Berapa banyak cara berbeda yang mungkin untuk mencapai puncak?

### Formulasi Matematis:
* **State**: `dp[i]` = jumlah cara unik mencapai anak tangga ke-`i`.
* **Base Cases**: `dp[1] = 1`, `dp[2] = 2`.
* **Recurrence Relation**: `dp[i] = dp[i-1] + dp[i-2]` (Anda bisa mencapai tangga ke-`i` dari tangga `i-1` dengan 1 langkah, atau dari tangga `i-2` dengan 2 langkah).

### Implementasi Lengkap (Python 3)

```python
from typing import Dict

class ClimbingStairs:
    
    # 1. Pendekatan Naif (Brute-Force Recursion)
    # Kompleksitas: Waktu O(2^N) | Ruang O(N) stack
    @staticmethod
    def climb_naive(n: int) -> int:
        if n <= 0:
            return 0
        if n == 1:
            return 1
        if n == 2:
            return 2
        return ClimbingStairs.climb_naive(n - 1) + ClimbingStairs.climb_naive(n - 2)

    # 2. Pendekatan Top-Down (Memoization)
    # Kompleksitas: Waktu O(N) | Ruang O(N) (memo + call stack)
    @staticmethod
    def climb_memo(n: int) -> int:
        memo: Dict[int, int] = {}

        def helper(step: int) -> int:
            if step <= 0:
                return 0
            if step == 1:
                return 1
            if step == 2:
                return 2
            
            if step in memo:
                return memo[step]
            
            memo[step] = helper(step - 1) + helper(step - 2)
            return memo[step]

        return helper(n)

    # 3. Pendekatan Bottom-Up (Tabulation)
    # Kompleksitas: Waktu O(N) | Ruang O(N)
    @staticmethod
    def climb_tabulation(n: int) -> int:
        if n <= 0:
            return 0
        if n == 1:
            return 1
        if n == 2:
            return 2

        dp = [0] * (n + 1)
        dp[1] = 1
        dp[2] = 2

        for i in range(3, n + 1):
            dp[i] = dp[i - 1] + dp[i - 2]

        return dp[n]

    # 4. Pendekatan Bottom-Up Space-Optimized
    # Kompleksitas: Waktu O(N) | Ruang O(1)
    @staticmethod
    def climb_optimized(n: int) -> int:
        if n <= 0:
            return 0
        if n == 1:
            return 1
        if n == 2:
            return 2

        prev2 = 1  # Merepresentasikan dp[i-2]
        prev1 = 2  # Merepresentasikan dp[i-1]

        for _ in range(3, n + 1):
            current = prev1 + prev2
            prev2 = prev1
            prev1 = current

        return prev1


if __name__ == "__main__":
    n = 10
    print(f"Hasil Naive ({n}):", ClimbingStairs.climb_naive(n))
    print(f"Hasil Memoization ({n}):", ClimbingStairs.climb_memo(n))
    print(f"Hasil Tabulation ({n}):", ClimbingStairs.climb_tabulation(n))
    print(f"Hasil Space-Optimized ({n}):", ClimbingStairs.climb_optimized(n))
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Masalah Nyata: Minimum Coin Change Problem (Sistem Kasir Otomatis)
Sebuah sistem *payment gateway* harus mengembalikan uang kembalian sejumlah $A$ (*amount*) menggunakan sesedikit mungkin keping koin dari himpunan denominasi koin yang tersedia: $C = [c_1, c_2, \dots, c_k]$. Asumsikan jumlah koin tiap denominasi tak terbatas. Jika kombinasi tidak memungkinkan, kembalikan `-1`.

### Formulasi Matematis
1. **State**: `dp[a]` = jumlah minimum koin yang diperlukan untuk menghasilkan jumlah uang `a`.
2. **Base Case**: `dp[0] = 0` (0 uang membutuhkan 0 koin).
3. **State Transition**:
   $$\text{dp}[a] = \min_{c \in C, \, a - c \ge 0} (\text{dp}[a - c] + 1)$$
4. **Ukuran Tabel**: Array berukuran $A + 1$, diinisialisasi dengan $\infty$ (*infinity*), kecuali `dp[0] = 0`.

### Kode Produksi Python dengan Traceback Solusi

```python
from typing import List, Tuple

class CoinChangeSolver:
    """
    Menyelesaikan masalah Coin Change menggunakan DP Tabulation lengkap
    dengan rekonstruksi koin yang terpilih (traceback).
    """

    @classmethod
    def compute_min_coins(cls, coins: List[int], amount: int) -> Tuple[int, List[int]]:
        """
        Mengembalikan tuple: (jumlah_minimum_koin, list_keping_koin)
        Jika tidak mungkin, mengembalikan (-1, [])
        """
        if amount < 0:
            return -1, []
        if amount == 0:
            return 0, []

        # Representasi tak hingga menggunakan integer sentinel
        INF = float('inf')
        
        # dp[i] menyimpan jumlah minimum koin untuk amount i
        dp = [INF] * (amount + 1)
        # parent[i] menyimpan denominasi koin terakhir yang dipakai untuk amount i
        parent = [-1] * (amount + 1)

        # Base case
        dp[0] = 0

        # Iterasi Bottom-Up
        for a in range(1, amount + 1):
            for coin in coins:
                if a - coin >= 0:
                    if dp[a - coin] + 1 < dp[a]:
                        dp[a] = dp[a - coin] + 1
                        parent[a] = coin

        # Jika target amount tidak dapat dicapai
        if dp[amount] == INF:
            return -1, []

        # Rekonstruksi solusi (Traceback)
        chosen_coins: List[int] = []
        curr = amount
        while curr > 0:
            coin_used = parent[curr]
            if coin_used == -1:
                # Keadaan anomali internal
                raise RuntimeError("Gagal merekonstruksi koin pada status valid.")
            chosen_coins.append(coin_used)
            curr -= coin_used

        return int(dp[amount]), chosen_coins


# Verifikasi Eksekusi
if __name__ == "__main__":
    denominations = [1, 2, 5]
    target_amount = 11

    min_coins, composition = CoinChangeSolver.compute_min_coins(denominations, target_amount)
    print(f"Denominasi yang tersedia: {denominations}")
    print(f"Target Kembalian       : Rp {target_amount}")
    print(f"Jumlah Koin Minimum    : {min_coins}")
    print(f"Kombinasi Koin         : {composition}")

    # Edge Case: Target yang mustahil dibentuk
    impossible_coins = [2, 4]
    target_impossible = 7
    res, comp = CoinChangeSolver.compute_min_coins(impossible_coins, target_impossible)
    print(f"\nUji Coba Mustahil: Target Rp {target_impossible} dengan {impossible_coins}")
    print(f"Hasil: {res} (Kombinasi: {comp})")
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Evaluasi | Top-Down (Memoization) | Bottom-Up (Tabulation) |
| :--- | :--- | :--- |
| **Alur Eksekusi** | Rekursif (Dimulai dari $N \to 0$) | Iteratif (Dimulai dari $0 \to N$) |
| **Penyimpanan Status** | On-demand (Hanya submasalah yang dikunjungi) | Exhaustive (Mengevaluasi semua status dalam domain) |
| **Efisiensi Overhead** | Lebih lambat karena *call stack frame* & fungsi rekursif | Lebih cepat, instruksi *loop* langsung pada CPU |
| **Batas Memori Stack** | Rentan terkena `RecursionError` / *Stack Overflow* pada $N > 10^4$ | Aman, memori dialokasikan pada heap array |
| **Kemudahan Formulasi** | Lebih natural, mencerminkan langsung persamaan matematis | Memerlukan perancangan urutan loop (*topological sort*) |
| **Optimasi Ruang** | Sangat sulit dioptimasi ruang karena dependensi tersebar | Relatif mudah direduksi (misal dengan array $1\text{D}$ atau variabel) |
| **Cache Locality** | Buruk jika menggunakan pointer/hash map (banyak cache misses) | Sangat baik karena pembacaan memori array berurutan (*contiguous memory*) |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Validasi Parameter Terlebih Dahulu**: Periksa input negatif, array kosong, atau kasus $N=0$ sebelum mengalokasikan memori tabel DP.
2. **Inisialisasi Nilai Default dengan Hati-hati**:
   * Masalah minimasi: Inisialisasi array dengan $\infty$ (`float('inf')` atau `INT_MAX`).
   * Masalah maksimasi: Inisialisasi dengan $-\infty$ atau `0` (jika nilai solusi non-negatif).
   * Masalah boolean/keberadaan: Inisialisasi dengan `False`.
3. **Pilihlah Struktur Array Primitif di atas Hash Map**: Penggunaan Hash Map untuk memoization memperkenalkan *overhead constant factor* dan potensi *hash collision*. Jika status berupa integer kontinu, gunakan array 1D/2D bertipe data rapat.
4. **Verifikasi Arah Dependensi Status**: Pastikan ketika menghitung status $i$, semua nilai pendukung (seperti $i-1$, $i-2$) sudah final dan tidak akan bermutasi lagi.
5. **Gunakan Rolling Arrays untuk Menghemat Memori**:
   Jika transisi matriks `dp[i][j]` hanya bergantung pada baris sebelumnya `dp[i-1][j]`, alokasikan memori berukuran $2 \times M$, alih-alih $N \times M$, menggunakan operator modulo: `dp[i % 2][j]`.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Off-by-One Error pada Ukuran Tabel
* **Salah**: `dp = [0] * n` lalu mengakses `dp[n]`.
* **Benar**: `dp = [0] * (n + 1)` jika status akhir adalah `n` dan diindeks dari 0.

### 2. Mengacaukan Masalah Greedy dengan DP
* **Salah**: Berasumsi bahwa koin terbesar selalu memberikan hasil optimal pada *Coin Change*.
  * *Contoh*: Denominasi $[1, 3, 4]$, Target $6$.
  * Greedy: $4 + 1 + 1 = 3$ koin.
  * DP (Optimal): $3 + 3 = 2$ koin.
  * *Solusi*: Selalu buktikan *greedy choice property* sebelum menolak pendekatan DP.

### 3. Mutasi State Global Saat Rekursi
Menggunakan variabel global yang termutasi pada cabang rekursif tanpa melakukan *backtracking*, yang merusak keabsahan nilai pada tabel memo.

### 4. Overwriting Values pada 1D Array Optimization
Pada kasus seperti *0/1 Knapsack* dengan optimasi array 1 dimensi:
* **Salah**: Iterasi kapasitas dari `0` menuju `W`. Ini membuat satu barang dapat diambil berulang kali (*Unbounded Knapsack behavior*).
* **Benar**: Iterasi kapasitas secara mundur dari `W` menuju `bobot_barang` untuk memastikan status yang dibaca adalah murni dari baris iterasi sebelumnya.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: House Robber (Tingkat: Easy)
* **Masalah**: Anda adalah seorang pencuri yang merencanakan perampokan di sepanjang jalan. Setiap rumah memiliki sejumlah uang tertentu. Dua rumah yang bertetangga memiliki sistem keamanan terhubung; jika dua rumah bersebelahan dirampok pada malam yang sama, alarm akan berbunyi secara otomatis.
* **Input**: `nums = [2, 7, 9, 3, 1]`
* **Output**: `12` (Rampok rumah 1, 3, dan 5: $2 + 9 + 1 = 12$)
* **Instruksi**: Tuliskan implementasi Tabulation dengan optimasi ruang $O(1)$.

### Latihan 2: Unique Paths (Tingkat: Medium)
* **Masalah**: Sebuah robot berada di sudut kiri atas dari grid berukuran $M \times N$ (titik $(0,0)$). Robot hanya bisa bergerak ke kanan atau ke bawah pada satu waktu. Robot mencoba mencapai sudut kanan bawah (titik $(M-1, N-1)$). Hitung berapa banyak kemungkinan jalur unik yang ada.
* **Batasan**: $1 \le M, N \le 100$. Solusi muat dalam tipe integer 32-bit.
* **Instruksi**: Rancang matriks DP 2D, lalu reduksi ruang memori menjadi 1D array berukuran $O(N)$.

### Latihan 3: Longest Increasing Subsequence (Tingkat: Hard)
* **Masalah**: Diberikan sebuah integer array `nums`, kembalikan panjang dari *subsequence* terpanjang yang naik secara tegas (*strictly increasing*).
* **Input**: `nums = [10, 9, 2, 5, 3, 7, 101, 18]`
* **Output**: `4` (Subsequence: `[2, 3, 7, 101]`)
* **Instruksi**: 
  1. Implementasikan solusi DP $O(N^2)$.
  2. *(Tantangan Lanjutan)*: Telusuri bagaimana algoritma DP ini dapat ditingkatkan menjadi $O(N \log N)$ dengan menggabungkan DP dengan *Binary Search* (Patience Sorting).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman Anda:

1. **Apa yang membedakan submasalah pada Dynamic Programming dengan submasalah pada Divide and Conquer?**
   * A. Dynamic Programming hanya menangani submasalah berskala besar.
   * B. Divide and Conquer memecah masalah menjadi submasalah independen, sedangkan DP menangani submasalah yang saling tumpang tindih (*overlapping*).
   * C. Divide and Conquer selalu menggunakan tabel iteratif.
   * D. DP tidak dapat diimplementasikan secara rekursif.
   * *Jawaban yang benar*: **B**.

2. **Kapan teknik Top-Down (Memoization) lebih unggul secara teoritis dibandingkan Bottom-Up (Tabulation)?**
   * A. Ketika semua kemungkinan status (*entire state space*) harus dievaluasi.
   * B. Ketika hanya sebagian kecil dari ruang status yang perlu dikunjungi untuk mencapai solusi akhir.
   * C. Ketika kedalaman rekursi melebihi batas call stack compiler.
   * D. Ketika cache locality prosesor merupakan prioritas utama.
   * *Jawaban yang benar*: **B**.

3. **Diberikan relasi rekurens: `dp[i][j] = dp[i-1][j] + dp[i][j-1]`. Berapa memori minimum yang diperlukan untuk menyelesaikan masalah ini secara Bottom-Up untuk grid $N \times M$?**
   * A. $O(N \times M)$
   * B. $O(N)$
   * C. $O(\min(N, M))$
   * D. $O(1)$
   * *Jawaban yang benar*: **C**. (Dengan orientasi baris atau kolom terkecil).

4. **Self-Check Checklist**:
   * [ ] Saya dapat membedakan kapan masalah harus diselesaikan dengan Greedy vs DP.
   * [ ] Saya mampu menuliskan persamaan matematis State Transition sebelum menulis baris kode pertama.
   * [ ] Saya memahami mengapa memoization mencegah rekursi eksponensial.
   * [ ] Saya mampu mengubah solusi rekursif memoized menjadi loop iteratif bottom-up.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Referensi**:
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.). MIT Press. — **Bab 14: Dynamic Programming**.
  * Kleinberg, J., & Tardos, É. (2006). *Algorithm Design*. Pearson. — **Bab 6: Dynamic Programming**.
  * Dasgupta, S., Papadimitriou, C., & Vazirani, U. (2006). *Algorithms*. McGraw-Hill. — **Bab 6: Dynamic programming**.
* **Makalah Akademik**:
  * Bellman, R. (1954). *The Theory of Dynamic Programming*. Bulletin of the American Mathematical Society, 60(6), 503-515.
* **Tautan Komputasi Daring**:
  * [MIT OpenCourseWare 6.006: Dynamic Programming I & II](https://ocw.mit.edu/)
  * [LeetCode Dynamic Programming Explore Card](https://leetcode.com/explore/featured/card/dynamic-programming/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
+-------------------------------------------------------------------------------+
|                        DYNAMIC PROGRAMMING CHEAT SHEET                        |
+-------------------------------------------------------------------------------+
| Karakteristik   | 1. Optimal Substructure: Solusi optimal mengandung solusi   |
| Kunci           |    submasalah optimal.                                      |
|                 | 2. Overlapping Subproblems: Masalah rekursif menghitung     |
|                 |    status yang sama berulang kali.                          |
+-----------------+-------------------------------------------------------------+
| Pendekatan      | Top-Down (Memoization):                                     |
| Solusi          |   - Alur: N -> Base Case                                    |
|                 |   - Struktur: Rekursi + Map/Array Cache                     |
|                 | Bottom-Up (Tabulation):                                     |
|                 |   - Alur: Base Case -> N                                    |
|                 |   - Struktur: Iterasi (Loop) + Array                        |
+-----------------+-------------------------------------------------------------+
| Alur            | 1. Tentukan State (misal: dp[i] = hasil optimal hingga i)   |
| Kerja Formulasi | 2. Identifikasi Base Case                                    |
|                 | 3. Konstruksi State Transition Equation                      |
|                 | 4. Hitung urutan pengisian tabel                            |
|                 | 5. Lakukan kompresi ruang memori jika memungkinkan         |
+-------------------------------------------------------------------------------+
```

---

## SEKSI 17 — GLOSARIUM

* **Optimal Substructure**: Karakteristik masalah di mana solusi optimal global dapat dibentuk secara matematis dari solusi optimal sub-submasalahnya.
* **Overlapping Subproblems**: Kondisi di mana cabang evaluasi pada pohon rekursi memanggil kembali fungsi rekursif dengan argumen parameter status yang persis sama.
* **Memoization**: Pendekatan optimasi pemanggilan fungsi top-down di mana hasil komputasi disimpan sementara dalam memori asosiatif atau array agar tidak dihitung ulang.
* **Tabulation**: Pendekatan perancangan tabel bottom-up di mana seluruh status diselesaikan langkah demi langkah secara iteratif dari kasus dasar menuju target.
* **State (Status)**: Himpunan parameter minimum yang secara utuh mendeskripsikan kondisi spesifik dari submasalah komputasi.
* **State Transition**: Persamaan rekurens yang mendefinisikan relasi ketergantungan antara satu status dengan status lainnya.
* **DAG (Directed Acyclic Graph)**: Struktur graf berarah tanpa siklus yang merepresentasikan hubungan dependensi status dalam dynamic programming.
* **Space Compression (Rolling Array)**: Teknik pemrograman yang mengabaikan histori status lampau dan hanya mempertahankan status aktif terdekat untuk memangkas konsumsi memori.
* **Call Stack**: Struktur data memori internal yang melacak titik kembali (*return address*) dari pemanggilan fungsi atau prosedur rekursif.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi**:
  * Mahasiswa sering kali melompat langsung menulis kode tanpa mendefinisikan *State* dalam bahasa manusia. Tekankan bahwa: *"Jika Anda tidak dapat mendefinisikan arti array `dp[i]` dengan kalimat yang presisi, Anda tidak akan pernah bisa menurunkan rumus transisinya secara konsisten."*
* **Titik Miskonsepsi Siswa**:
  * Mengira bahwa semua optimasi rekursi adalah DP. Tunjukkan bahwa Divide & Conquer (seperti Merge Sort) memecah masalah secara terpisah tanpa ada submasalah yang bertumpang tindih (*non-overlapping*), sehingga tabel memoization tidak berguna di sana.
* **Aktivitas Interaktif di Kelas**:
  * Minta peserta menggambar pohon pemanggilan fungsi rekursif pada papan tulis untuk $N=4$ pada masalah *Climbing Stairs*, lalu lingkari dengan spidol merah setiap kali mereka menuliskan simpul yang identik. Ini secara instan memvisualisasikan pemborosan komputasi eksponensial.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0 (Stabil)
* **Tanggal Rilis**: 2025-01-15
* **Author**: Senior Technical Curriculum Architect
* **Catatan Perubahan**:
  * `v1.0.0`: Pembuatan rilis awal modul Dynamic Programming Fundamentals lengkap dengan 20 seksi standar kurikulum, analisis kompleksitas, studi kasus *Climbing Stairs*, dan implementasi produksi *Coin Change* dengan penelusuran traceback.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* ⬅️ **Modul Sebelumnya**: DSA-01-07-001 (Greedy Algorithms & Matroid Theory)
* ➡️ **Modul Berikutnya**: DSA-01-08-002 (Classic DP: 0/1 Knapsack, Unbounded Knapsack, and Subset Sum)
* 📑 **Daftar Bab**: 01-Core-Foundations / Bab 08: Dynamic Programming / Modul 01