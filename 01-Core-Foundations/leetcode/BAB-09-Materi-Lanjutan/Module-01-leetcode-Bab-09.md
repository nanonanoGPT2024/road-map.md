# Kurikulum LeetCode: Dynamic Programming & Exhaustive Search

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Algorithmic Problem Solving & Technical Interview Mastery
* **Kategori:** `01-Core-Foundations`
* **Bab 09:** Dynamic Programming & Exhaustive Search
* **Modul 01:** Paradigma Dynamic Programming: Dekonstruksi Rekursi, Overlapping Subproblems, dan Formulasi State
* **Tingkat Kesulitan:** Intermediate to Advanced
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang Rekursi dan Call Stack (`01-Core-Foundations/Bab 05: Recursion & Backtracking`).
  * Analisis Asimptotik Kompleksitas Waktu dan Ruang (Big-O Notation).
  * Struktur Data Dasar: Array, Hash Table, dan Tree Traversal.
* **Target LeetCode Patterns:**
  * 1D Dynamic Programming (Linear DP)
  * Decision Making at Each Step (Include/Exclude, Pick/Don't Pick)
  * Top-Down Memoization vs. Bottom-Up Tabulation Transition
  * State Space Reduction (Space Optimization)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendiagnosis Karakteristik Masalah DP:** Mengidentifikasi secara matematis keberadaan *Optimal Substructure* dan *Overlapping Subproblems* pada sebuah deskripsi masalah tanpa bergantung pada intuisi semata.
2. **Merancang Ruang State (State Space):** Mendefinisikan variabel status ($DP[i]$ atau $DP[i][j]$) secara presisi dengan representasi semantik yang tidak ambigu.
3. **Menurunkan Persamaan Transisi State (Recurrence Relation):** Memetakan relasi antar sub-masalah dari pendekatan brute-force rekursif menjadi formulasi transisi matematis formal.
4. **Mengimplementasikan Dual Approach:** Mengonversi solusi *Exhaustive Search* eksponensial ($O(2^n)$ atau $O(k^n)$) menjadi:
   * Top-Down DP dengan Memoization ($O(n)$ time, $O(n)$ recursion stack + cache).
   * Bottom-Up DP dengan Tabulation ($O(n)$ time, $O(n)$ table).
5. **Melakukan Optimasi Ruang (Space Compression):** Mereduksi kompleksitas memori dari $O(n)$ menjadi $O(1)$ atau dari $O(n \times m)$ menjadi $O(m)$ menggunakan teknik *rolling variables* atau *sliding buffer*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [Problem Domain]
                              |
                 Is it an Optimization/Counting
                      Decision Problem?
                              |
               +--------------+--------------+
               |                             |
              YES                            NO -> [Divide & Conquer / Greedy / Simulation]
               |
    Check Two Vital Properties:
    1. Optimal Substructure?
    2. Overlapping Subproblems?
               |
         +-----+-----+
         |           |
        YES          NO -> [Backtracking / Pure DFS / Branch & Bound]
         |
    [DYNAMIC PROGRAMMING]
         |
         +---> 1. STATE FORMULATION: Define semantics of DP[state]
         |
         +---> 2. TRANSITION RELATION: DP[state] = f(DP[prior_states])
         |
         +---> 3. BASE CASES: Smallest solvable sub-instances
         |
         +---> 4. EVALUATION ORDER:
                     |
         +-----------+-----------+
         |                       |
     [TOP-DOWN]             [BOTTOM-UP]
  (Recursive + Memo)      (Iterative Table)
         |                       |
   Lazy Evaluation         Eager Evaluation
   Call Stack Overhead     Cache-Locality Friendly
                                 |
                          [OPTIMIZATION]
                          Space Reduction
                      (Rolling Array / O(1))
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dynamic Programming (DP) adalah pembeda utama antara kandidat level pemula dengan level senior dalam wawancara rekayasa perangkat lunak tingkat elit (FAANG/Tier-1). Masalah optimasi (menemukan nilai minimum/maksimum), penghitungan kombinatorik (menghitung jumlah cara yang valid), dan penentuan kelayakan (*boolean reachability*) sering kali berujung pada *Exhaustive Search* (pencarian tuntas). 

Secara naif, pencarian tuntas mengeksplorasi seluruh pohon keputusan (*decision tree*), menghasilkan kompleksitas waktu eksponensial seperti $O(2^N)$ atau faktorial $O(N!)$. Dalam sistem berskala besar atau batasan runtime ketat LeetCode ($N = 10^5$), algoritma eksponensial akan mengalami *Time Limit Exceeded* (TLE) bahkan untuk input sekecil $N = 40$.

DP memformalkan prinsip penghitungan efisien: **"Jangan pernah menghitung kembali apa yang sudah pernah diselesaikan."** Dengan mengidentifikasi *Overlapping Subproblems*, DP mentransformasi pohon komputasi rekursif menjadi *Directed Acyclic Graph* (DAG), mereduksi kompleksitas waktu dari eksponensial menjadi polinomial ($O(N)$, $O(N^2)$, atau $O(N \times K)$). Memahami DP dari akarnya memungkinkan seorang insinyur untuk mendesain sistem dengan efisiensi komputasi optimal secara sistematis, bukan melalui tebakan (*trial and error*).

---

## SEKSI 05 — APA ITU (WHAT)

Secara formal, **Dynamic Programming** adalah paradigma perancangan algoritma di mana suatu masalah diselesaikan dengan memecahnya menjadi sub-masalah yang tumpang tindih (*overlapping subproblems*), menyelesaikan masing-masing sub-masalah tepat satu kali, dan menyimpan solusinya untuk digunakan di masa mendatang.

### Dua Pilar Utama Dynamic Programming

1. **Optimal Substructure (Substruktur Optimal):**
   Sebuah masalah memiliki substruktur optimal jika solusi optimal global untuk masalah tersebut dapat dibangun secara deterministik dari solusi-solusi optimal dari sub-masalahnya.
   * *Contoh:* Jalur terpendek dari titik A ke titik C melalui B ($A \to B \to C$) hanya bisa optimal jika jalur dari A ke B optimal DAN jalur dari B ke C juga optimal.
   * *Bukan Optimal Substructure:* Jalur terpanjang tanpa siklus (Longest Simple Path) tidak memiliki sifat ini karena pemilihan simpul di sub-masalah A ke B dapat membatasi pilihan simpul yang tersedia untuk sub-masalah B ke C.

2. **Overlapping Subproblems (Sub-masalah Tumpang Tindih):**
   Sebuah masalah memiliki sub-masalah yang tumpang tindih jika pohon rekursif dari *Exhaustive Search* mengunjungi konfigurasi status (*state*) yang persis sama berulang kali dengan parameter input yang identik.
   * Jika sub-masalah bersifat independen secara total (seperti pada *Merge Sort*), paradigma yang tepat adalah *Divide and Conquer*, bukan DP.
   * DP mengeksploitasi redundansi ini dengan mencatat (*memoizing*) hasil penghitungan status yang sudah pernah dievaluasi.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Perancangan algoritma DP dilakukan melalui **Framework 4 Langkah Sistematis**:

### Langkah 1: State Definition (Definisi Status)
Tentukan apa yang direpresentasikan oleh $DP[i]$ atau $DP[i][j]$. Definisi ini harus eksplisit dan menyertakan batasan domain secara presisi.
* *Contoh:* "$DP[i]$ adalah biaya minimum absolut untuk mencapai anak tangga ke-$i$."

### Langkah 2: State Transition Function (Fungsi Transisi Status / Recurrence)
Tentukan bagaimana nilai status saat ini diturunkan dari status-status sebelumnya yang telah terhitung. Identifikasi ruang keputusan (*choice set*).
* *Rumus umum:*
  $$DP[\text{state}] = \min_{\text{choice} \in \text{Choices}} \Big( \text{cost}(\text{choice}) + DP[\text{state}'(\text{choice})] \Big)$$

### Langkah 3: Base Cases & Initialization (Kondisi Dasar & Inisialisasi)
Tentukan nilai batas di mana masalah dapat diselesaikan secara trivial tanpa perlu didekomposisi lebih lanjut.
* Berikan perhatian khusus pada inisialisasi status yang tidak valid atau belum terjangkau (misalnya mengisi tabel dengan $\infty$ atau $-\infty$).

### Langkah 4: Direction of Computation (Arah Evaluasi)
* **Top-Down (Memoization):** Evaluasi dimulai dari target akhir menuju *base cases* melalui tumpukan rekursi. Cache (hash map atau array) diperiksa sebelum menghitung:
  ```
  f(n):
    if n in memo: return memo[n]
    if base_case(n): return base_value
    memo[n] = calculate(f(n-1), f(n-2), ...)
    return memo[n]
  ```
* **Bottom-Up (Tabulation):** Evaluasi dimulai dari *base cases* menuju target akhir secara iteratif menggunakan loop. Mengisi array/tabel secara terurut berdasarkan ketergantungan topologis:
  ```
  dp[0] = base_value
  for i from 1 to n:
      dp[i] = transition(dp[i-1], dp[i-2], ...)
  return dp[n]
  ```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Pohon Rekursi Naif (Exhaustive Search) vs. Directed Acyclic Graph (DAG)

Menghitung deret Fibonacci $F(5)$ secara naif memicu duplikasi komputasi eksponensial ($O(2^n)$):

```
                                  F(5)
                             /            \
                        F(4)                F(3)*
                      /      \             /     \
                  F(3)*      F(2)**      F(2)**   F(1)
                 /    \      /    \      /    \
              F(2)**  F(1) F(1)   F(0)  F(1)  F(0)
             /    \
           F(1)   F(0)

  [*] Menandakan F(3) dihitung 2 kali secara independen.
  [**] Menandakan F(2) dihitung 3 kali secara independen.
```

Dengan mengidentifikasi status yang berulang, kita mengubah pohon di atas menjadi **DAG** terkompresi dengan $O(N)$ node:

```
  [Base: F(0)=0] -----> [ F(2) ] -----> [ F(4) ]
         |             ^   |           ^   |
         v            /    v          /    v
  [Base: F(1)=1] ----+    [ F(3) ] --+   [ F(5) ] (Target)
```

### 2. State Transition Pipeline (Coin Change / Step Reduction)

```
  Index:       0       1       2       3       4       5
  Array:    [  0  ] [  1  ] [  1  ] [  2  ] [  2  ] [  3  ]
               |       ^       ^       ^       ^       ^
               |       |       |       |       |       |
  Decisions: Base   1 coin   1 coin  2 coins 2 coins 3 coins
                    (val 1)  (val 2) (1+2/3) (2+2)   (min-path)
                                         |
  Transition: DP[i] = 1 + min(DP[i - c_1], DP[i - c_2], ...)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Masalah: LeetCode 70 — Climbing Stairs

> Anda sedang menaiki tangga. Dibutuhkan $n$ langkah untuk mencapai puncak. Setiap kali melangkah, Anda dapat memilih melangkah 1 anak tangga atau 2 anak tangga. Berapa banyak cara berbeda yang tersedia untuk mencapai puncak?

#### 1. Pendekatan Rekursif Murni (Exhaustive Search - Brute Force)
* **Kompleksitas Waktu:** $O(2^n)$ — Membentuk pohon biner penuh.
* **Kompleksitas Ruang:** $O(n)$ — Alokasi tumpukan rekursi (*call stack*).

```python
class SolutionBruteForce:
    def climbStairs(self, n: int) -> int:
        """
        Mengevaluasi seluruh cabang keputusan secara tuntas.
        PERINGATAN: TLE pada n >= 40.
        """
        def recurse(current_step: int) -> int:
            if current_step == n:
                return 1
            if current_step > n:
                return 0
            return recurse(current_step + 1) + recurse(current_step + 2)
            
        return recurse(0)
```

#### 2. Pendekatan Top-Down DP (Memoization)
* **Kompleksitas Waktu:** $O(n)$ — Setiap status dari $0$ hingga $n$ hanya dievaluasi satu kali.
* **Kompleksitas Ruang:** $O(n)$ — Hash map/array memoization berukuran $n$ + tumpukan rekursi $O(n)$.

```python
from typing import Dict

class SolutionTopDown:
    def climbStairs(self, n: int) -> int:
        memo: Dict[int, int] = {}

        def recurse(step: int) -> int:
            # Base Cases
            if step == n:
                return 1
            if step > n:
                return 0
            
            # Lookup Cache
            if step in memo:
                return memo[step]
            
            # State Transition: f(i) = f(i+1) + f(i+2)
            memo[step] = recurse(step + 1) + recurse(step + 2)
            return memo[step]

        return recurse(0)
```

#### 3. Pendekatan Bottom-Up DP (Tabulation)
* **Kompleksitas Waktu:** $O(n)$ — Single linear pass loop.
* **Kompleksitas Ruang:** $O(n)$ — Array tabel DP berukuran $n + 1$.

```python
class SolutionBottomUp:
    def climbStairs(self, n: int) -> int:
        if n <= 2:
            return n

        # dp[i] merepresentasikan jumlah cara unik mencapai anak tangga ke-i
        dp = [0] * (n + 1)
        
        # Base Cases
        dp[1] = 1
        dp[2] = 2

        # Iterasi dari dependensi terkecil ke terbesar
        for i in range(3, n + 1):
            dp[i] = dp[i - 1] + dp[i - 2]

        return dp[n]
```

#### 4. Pendekatan Optimized Bottom-Up DP (Space Optimization)
* **Kompleksitas Waktu:** $O(n)$
* **Kompleksitas Ruang:** $O(1)$ — Hanya menyimpan dua status sebelumnya (*rolling variables*).

```python
class SolutionSpaceOptimized:
    def climbStairs(self, n: int) -> int:
        if n <= 2:
            return n

        prev2 = 1  # Merepresentasikan dp[i-2]
        prev1 = 2  # Merepresentasikan dp[i-1]

        for _ in range(3, n + 1):
            current = prev1 + prev2
            prev2 = prev1
            prev1 = current

        return prev1
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Masalah: LeetCode 322 — Coin Change

> Diberikan array bilangan bulat `coins` yang merepresentasikan pecahan koin yang berbeda, dan bilangan bulat `amount` yang merepresentasikan total uang. Kembalikan *jumlah koin paling sedikit* yang Anda butuhkan untuk menyusun nilai `amount` tersebut. Jika jumlah tersebut tidak dapat dicapai oleh kombinasi koin apa pun, kembalikan `-1`. Diasumsikan persediaan setiap jenis koin tidak terbatas (*unbounded*).

#### Formulasi Matematis:
* **State:** $DP[i]$ menyatakan jumlah koin minimum yang dibutuhkan untuk membentuk nilai $i$.
* **Base Case:** $DP[0] = 0$ (membutuhkan 0 koin untuk membentuk nilai 0).
* **State Transition:**
  $$DP[i] = \min_{c \in \text{coins}, i - c \ge 0} \big( DP[i - c] + 1 \big)$$
* Jika nilai tidak dapat dicapai, $DP[i] = \infty$.

#### Implementasi Produksi (Tabulation):

```python
from typing import List

class SolutionCoinChange:
    def coinChange(self, coins: List[int], amount: int) -> int:
        """
        Menyelesaikan masalah Unbounded Knapsack variant menggunakan Bottom-Up DP.
        
        Kompleksitas Waktu: O(amount * len(coins))
        Kompleksitas Ruang: O(amount)
        """
        # Validasi batas input ekstrem
        if amount < 0:
            return -1
        if amount == 0:
            return 0

        # Inisialisasi DP table dengan sentinel value: amount + 1 (merepresentasikan infinity)
        # Mengapa amount + 1? Karena solusi valid tidak akan pernah melebihi amount koin (pecahan minimum adalah 1).
        INF = amount + 1
        dp = [INF] * (amount + 1)
        
        # Base case
        dp[0] = 0

        # Evaluasi iteratif dari nilai terkecil 1 hingga amount
        for current_amount in range(1, amount + 1):
            for coin in coins:
                # Periksa apakah koin valid untuk digunakan
                if current_amount - coin >= 0:
                    # Relasi transisi: pilih minimum antara state yang sudah ada
                    # atau menggunakan coin saat ini + solusi optimal dari sisa nilai (current_amount - coin)
                    dp[current_amount] = min(
                        dp[current_amount], 
                        dp[current_amount - coin] + 1
                    )

        # Jika dp[amount] tetap bernilai INF, berarti tidak ada kombinasi yang valid
        return dp[amount] if dp[amount] != INF else -1
```

#### Analisis Trace Eksekusi:
Misalkan `coins = [1, 2, 5]`, `amount = 5`:

| Step ($i$) | Koin yang Diuji | Evaluasi Formula | $DP[i]$ Hasil |
|---|---|---|---|
| $0$ | - | Kondisi Dasar | **0** |
| $1$ | 1 | $\min(\infty, DP[0] + 1) = 1$ | **1** |
| $2$ | 1, 2 | $\min(DP[1]+1, DP[0]+1) = \min(2, 1)$ | **1** |
| $3$ | 1, 2 | $\min(DP[2]+1, DP[1]+1) = \min(2, 2)$ | **2** |
| $4$ | 1, 2 | $\min(DP[3]+1, DP[2]+1) = \min(3, 2)$ | **2** |
| $5$ | 1, 2, 5 | $\min(DP[4]+1, DP[3]+1, DP[0]+1) = \min(3, 3, 1)$ | **1** |

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Evaluasi | Top-Down DP (Memoization) | Bottom-Up DP (Tabulation) |
|---|---|---|
| **Pola Eksekusi** | Rekursif (*On-Demand / Lazy*) | Iteratif (*Systematic / Eager*) |
| **Alokasi Memori** | Lebih tinggi: Hash Map/Array + Call Stack ($O(N)$ overhead) | Lebih rendah: Array statis tanpa Call Stack |
| **Batas Rekursi** | Rentan terhadap `RecursionError` / Stack Overflow pada $N > 1000$ | Bebas risiko Stack Overflow |
| **Kemudahan Logika** | Intuisi turunan langsung dari *brute force* rekursi | Butuh penentuan urutan traversal topologis eksplisit |
| **Efisiensi Status** | Hanya mengevaluasi sub-masalah yang benar-benar tercapai | Mengevaluasi semua sub-masalah dari 0 hingga $N$ |
| **Optimasi Ruang** | Sulit dioptimasi menjadi $O(1)$ atau $O(k)$ | Sangat mudah dioptimasi via teknik *rolling array* |
| **Cache Locality** | Buruk (akses memori tidak kontinu/pointer indirection) | Sangat baik (akses array kontinu ramah CPU cache) |

---

## SEKSI 11 — BEST PRACTICES

1. **Definisikan Tipe dan Batas Status (State Boundaries):**
   Gunakan type hint eksplisit. Tentukan ukuran array tabel sebesar `size + 1` untuk menghindari pergeseran indeks 1-based yang rentan bug.
2. **Gunakan Sentinel Value yang Aman:**
   Hindari penggunaan `float('inf')` jika operasi penjumlahan dapat memicu *overflow* pada bahasa berpengetikan statis (misal C++/Java). Di Python, gunakan `amount + 1` atau `float('inf')` dengan validasi aman.
3. **Pilih Top-Down saat Ruang State Sparse:**
   Jika hanya sebagian kecil sub-masalah yang dikunjungi dalam ruang pencarian besar, Top-Down Memoization lebih cepat secara signifikan karena mengabaikan status yang tidak terjangkau.
4. **Pilih Bottom-Up saat State Dense:**
   Jika hampir semua status harus dihitung, gunakan Bottom-Up untuk mendapatkan keuntungan performa dari *loop unrolling*, *cache locality*, dan ketiadaan overhead *frame stack*.
5. **Ekstrak Pola Transisi Sebelum Menulis Kode:**
   Tuliskan relasi rekursif di atas kertas atau komentar dokumen sebelum mengimplementasikan array atau perulangan.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Kegagalan Base Case:**
   * Lupa mendefinisikan kondisi terminasi untuk status 0 atau nilai negatif, memicu rekursi tak hingga (*infinite recursion*) atau nilai awal yang merusak hasil min/max.
2. **Urutan Loop Terbalik (Wrong Iteration Order):**
   * Menghitung $DP[i]$ sebelum status dependensinya ($DP[i-1]$ atau $DP[i-2]$) selesai dievaluasi, menghasilkan pembacaan memori sampah (*uninitialized values*).
3. **Kekeliruan Argumen Memoization:**
   * Pada fungsi rekursif dengan beberapa argumen, lupa memasukkan semua parameter pembeda status ke dalam kunci cache memo (contoh: hanya meng-cache indeks array, padahal kapasitas yang tersisa juga berubah).
4. **Mencampuradukkan Semantik Array:**
   * Contoh: Mengartikan $DP[i]$ sebagai "nilai pada indeks $i$" di satu baris fungsi, lalu mengartikannya sebagai "panjang hingga elemen ke-$i$" di baris lain.
5. **Pengabaian Masalah Reconstructive Solution:**
   * Banyak masalah menuntut *jalur optimal* dan bukan sekadar *biaya optimal*. Menimpa status tanpa menyimpan pelacak jejak (*parent tracking array*) membuat rekonstruksi solusi menjadi mustahil dilakukan.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Easy): LeetCode 746 — Min Cost Climbing Stairs
* **Deskripsi:** Diberikan array integer `cost` di mana `cost[i]` adalah biaya anak tangga ke-$i$. Setelah membayar biaya tersebut, Anda dapat melangkah satu atau dua tangga. Temukan biaya minimum untuk mencapai puncak tangga (melampaui indeks terakhir).
* **Tantangan:** Terapkan solusi Tabulation dengan optimasi ruang $O(1)$.

### Latihan 2 (Medium): LeetCode 198 — House Robber
* **Deskripsi:** Seorang pencuri merencanakan perampokan rumah di sepanjang jalan. Setiap rumah menyimpan sejumlah uang. Rumah-rumah tersebut memiliki sistem alarm terhubung yang akan memicu alarm jika dua rumah bersebelahan dibobol pada malam yang sama.
* **Tantangan:** Rancang state $DP[i]$ dan transisi yang merepresentasikan pilihan: *Rampok rumah saat ini vs Lewati rumah saat ini*. Capai kompleksitas $O(N)$ waktu dan $O(1)$ ruang.

### Latihan 3 (Medium-Hard): LeetCode 416 — Partition Equal Subset Sum
* **Deskripsi:** Diberikan array bilangan bulat `nums`, tentukan apakah array tersebut dapat dipartisi menjadi dua subset sehingga jumlah elemen di kedua subset tersebut sama persis.
* **Tantangan:** Konversi masalah ini menjadi varian *0/1 Knapsack Decision Problem*. Terapkan optimasi ruang dari tabel 2D menjadi 1D array terbalik (*reverse iteration*).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

#### Pertanyaan:
1. Mengapa *Merge Sort* tidak dikategorikan sebagai algoritma Dynamic Programming meskipun memecah masalah menjadi sub-masalah yang lebih kecil?
2. Kapan teknik optimasi ruang *Rolling Array* ($O(1)$ memory) **tidak** dapat diterapkan pada algoritma Bottom-Up DP?
3. Dalam masalah *Unbounded Knapsack*, arah traversal loop kapasitas bergerak maju ($0 \to W$), sedangkan pada *0/1 Knapsack* bergerak mundur ($W \to 0$). Mengapa demikian?
4. Apa yang terjadi jika tabel DP diinisialisasi dengan angka `0` alih-alih `float('inf')` pada masalah minimisasi biaya?
5. Sebuah pohon keputusan rekursif memiliki kedalaman $N$ dengan faktor percabangan $K$. Berapa batas atas kompleksitas waktu *brute-force* vs DP jika hanya ada $N$ status unik?

---

#### Jawaban & Analisis:
1. **Analisis:** *Merge Sort* membagi masalah menjadi sub-masalah yang sepenuhnya independen dan disjoin. Tidak ada *Overlapping Subproblems* (tidak ada irisan sub-masalah yang dihitung ulang), sehingga paradigma yang tepat adalah murni *Divide and Conquer*.
2. **Analisis:** Optimasi ruang *rolling variables* hanya dapat diterapkan jika transisi status saat ini hanya bergantung pada sejumlah konstan ($k$) baris/langkah sebelumnya. Jika transisi memerlukan akses acak ke seluruh status historis dari $0$ hingga $i-1$ (seperti pada *Longest Increasing Subsequence* $O(N^2)$), array berukuran $N$ wajib dipertahankan.
3. **Analisis:** Iterasi maju ($0 \to W$) memungkinkan satu elemen koin/item digunakan berkali-kali dalam iterasi yang sama (karena $DP[w - c]$ sudah memperhitungkan item saat ini). Iterasi mundur ($W \to 0$) memastikan bahwa status $DP[w - c]$ yang dibaca masih murni dari evaluasi iterasi sebelumnya, menjamin bahwa setiap item maksimal hanya dipilih tepat satu kali (karakteristik mutlak 0/1 Knapsack).
4. **Analisis:** Fungsi `min(dp[i], dp[i-c] + cost)` akan selalu memilih `0` karena nilai awal `0` lebih kecil dari biaya positif apa pun, sehingga algoritma gagal memperbarui nilai ke jalur yang benar.
5. **Analisis:** *Brute-force* membutuhkan waktu $O(K^N)$ (eksponensial). DP mereduksinya menjadi perkalian dari jumlah status unik dengan biaya transisi per status: $O(N \times K)$, yang merupakan fungsi polinomial linear.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku:**
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.), Chapter 14: Dynamic Programming. MIT Press.
  * Kleinberg, J., & Tardos, É. (2006). *Algorithm Design*, Chapter 6: Dynamic Programming. Pearson.
* **Paper Ilmiah:**
  * Bellman, Richard (1954). "The Theory of Dynamic Programming". *Bulletin of the American Mathematical Society*, 60(6): 503–515.
* **LeetCode Explore Card:**
  * LeetCode Official Dynamic Programming Category & Study Plans (Dynamic Programming I & II).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
        RECURSION TREE                  MEMOIZATION TABLE                  1D TABULATION
         (Exhaustive)                      (Top-Down)                       (Bottom-Up)
             (4)                         [k:4] -> mem[4]                     +---+---+---+---+---+
           /     \                       [k:3] -> mem[3]             DP:     | 0 | 1 | 2 | 3 | 5 |
         (3)     (2)                     [k:2] -> mem[2]                     +---+---+---+---+---+
        /   \   /   \                    [k:1] -> mem[1]                       0   1   2   3   4
      (2)  (1) (1)  (0)                  Evaluasi: Saat dipanggil            Evaluasi: Iterasi loop
    (Duplikasi eksponensial)            Memory: O(N) + Stack O(N)           Memory: O(N) -> O(1)
```

1. Dynamic Programming adalah teknik optimasi sistematis yang mengubah masalah pohon rekursif eksponensial menjadi traversal DAG polinomial.
2. Keberhasilan DP menuntut dua prasyarat mutlak: **Optimal Substructure** dan **Overlapping Subproblems**.
3. Pendekatan **Top-Down** bertumpu pada rekursi dan struktur cache (*lazy evaluation*), sedangkan pendekatan **Bottom-Up** menyusun komputasi dari kondisi batas menggunakan iterasi (*eager evaluation*).
4. Pemilihan formulasi *state* adalah langkah paling fundamental. Jika definisi status ambigu, maka penyusunan fungsi transisi dipastikan keliru.
5. Optimasi ruang (*space optimization*) harus selalu dipertimbangkan pada evaluasi Bottom-Up dengan menganalisis dependensi indeks status sebelumnya.

---

## SEKSI 17 — GLOSARIUM

* **Exhaustive Search:** Metode penelusuran ruang pencarian dengan memeriksa seluruh kemungkinan kandidat solusi secara lengkap.
* **State (Status):** Konfigurasi atau parameter minimal yang diperlukan untuk mengidentifikasi suatu sub-masalah secara unik.
* **Recurrence Relation:** Persamaan matematis rekursif yang mendefinisikan suatu nilai status berdasarkan status-status lain yang mendahuluinya.
* **Overlapping Subproblems:** Kondisi di mana suatu algoritma dekomposisi berulang kali menyelesaikan sub-masalah yang persis sama.
* **Optimal Substructure:** Karakteristik sistemik di mana solusi optimal global memuat solusi optimal dari sub-masalahnya.
* **Memoization:** Teknik optimasi top-down dengan menyimpan hasil pemanggilan fungsi yang berbiaya komputasi tinggi dan mengembalikannya langsung saat parameter masukan yang sama terjadi lagi.
* **Tabulation:** Teknik optimasi bottom-up dengan mengisi tabel komputasi secara linier atau multi-dimensi sesuai urutan ketergantungan topologis.
* **Space Compression (Rolling Array):** Teknik reduksi penggunaan memori tabel DP dengan hanya menyimpan status yang secara langsung dibutuhkan untuk iterasi berikutnya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Jebakan Mental Siswa:** Mayoritas pemula mencoba menghafal kode implementasi alih-alih menguasai **semantik state**. Tekankan kepada siswa untuk selalu menuliskan deskripsi satu kalimat: *"Apa arti dari $DP[i]$?"* sebelum menulis satu baris kode pun.
* **Titik Krusial Analisis:** Saat beralih dari rekursi murni ke Bottom-Up, sering terjadi kebingungan mengenai batas loop (`range(1, n+1)` vs `range(n)`). Biasakan siswa menggambar tabel secara manual untuk input $n=3$ atau $n=4$ di kertas.
* **Praktek Terbaik Pedagogis:** Tunjukkan degradasi performa secara nyata dengan menjalankan brute force $F(45)$ yang memakan waktu belasan detik vs solusi DP yang selesai dalam fraksi milidetik, untuk menanamkan pemahaman intuitif mengenai efisiensi asimptotik.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2026):**
  * Rilis modul awal standar GEMINI.md.
  * Dekonstruksi komprehensif Rekursi, Memoization, Tabulation, dan Space Compression.
  * Penyediaan contoh kode produksi LeetCode 70 (Climbing Stairs) dan LeetCode 322 (Coin Change).
  * Standarisasi 20 seksi lengkap tanpa pemotongan materi.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `01-Core-Foundations/Bab 08: Tree & Graph Traversals/Module 03: Topological Sort & Strongly Connected Components`
* **Modul Saat Ini:** `01-Core-Foundations/Bab 09: Dynamic Programming & Exhaustive Search/Module 01: Paradigma Dynamic Programming: Dekonstruksi Rekursi, Overlapping Subproblems, dan Formulasi State`
* **Modul Berikutnya:** `01-Core-Foundations/Bab 09: Dynamic Programming & Exhaustive Search/Module 02: Pola Klasik 1D DP: Longest Increasing Subsequence (LIS) & Partitioning Problems`