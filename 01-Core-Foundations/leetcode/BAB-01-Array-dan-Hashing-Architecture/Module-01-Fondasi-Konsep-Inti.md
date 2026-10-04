# Bab 01: Fondasi Algoritmik & Problem Solving LeetCode
## Modul 01: Analisis Kompleksitas Asimptotik & Mental Model Dekonstruksi Masalah

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mengidentifikasi** batas runtime dan memori berdasarkan batasan input (*constraints*) yang tertera pada problem statement LeetCode.
- **Menganalisis** kompleksitas waktu (*Time Complexity*) dan ruang (*Space Complexity*) algoritma menggunakan notasi Big-O, Big-$\Omega$, dan Big-$\Theta$ secara matematis dan praktis.
- **Menghitung** *Amortized Time Complexity* pada struktur data dinamis menggunakan *Aggregate Method* dan *Banker's/Accounting Method*.
- **Membangun** *mental model* dekonstruksi masalah 5 langkah untuk mencegah kesalahan logika sebelum menulis baris kode pertama.
- **Menghindari** status *Time Limit Exceeded* (TLE) dan *Memory Limit Exceeded* (MLE) melalui estimasi operasi per detik pada runtime engine LeetCode.

---

### 2. Konsep Inti (Core Concept)
Fondasi kompetensi algoritma kompetitif tidak berakar pada hafalan sintaksis, melainkan pada **Analisis Asimptotik** dan **Pemetaan Batasan Masalah (*Constraint Mapping*)**. 

Analisis asimptotik mengukur laju pertumbuhan (*growth rate*) kebutuhan sumber daya (waktu eksekusi dan alokasi memori) terhadap pertambahan ukuran input ($N$) saat $N \to \infty$. Di platform seperti LeetCode, setiap soal memiliki *time limit* absolut (biasanya 1.0–2.0 detik) dan *memory limit* (biasanya 256MB–512MB). Menguasai hubungan antara nilai $N$ dengan kompleksitas target adalah filter primer dalam menentukan arsitektur algoritma yang valid.

---

### 3. Mengapa Ini Penting (Why It Matters)
Mesin penilai (*judge system*) LeetCode mengeksekusi kode Anda melawan puluhan hingga ratusan *test cases*, termasuk *corner cases* dan *extreme large inputs*. 

* CPU modern pada server LeetCode rata-rata mampu memproses sekitar **$10^7$ hingga $10^8$ operasi dasar per detik** (tergantung bahasa: C++ lebih dekat ke $10^8$, Python berkisar antara $10^6 - 10^7$).
* Menulis algoritma $O(N^2)$ untuk input berukuran $N = 10^5$ akan menghasilkan $(10^5)^2 = 10^{10}$ operasi. Eksekusi ini membutuhkan waktu sekitar $100$ detik, yang secara deterministik memicu status **Time Limit Exceeded (TLE)**.
* Memahami analisis asimptotik secara apriori memungkinkan Anda membuang pendekatan yang salah sebelum mengetik sebaris kode pun.

---

### 4. Apa Sebenarnya Ini? (What It Actually Is)
Secara formal, analisis asimptotik mendefinisikan batas matematis atas fungsi komputasi:

* **Big-O ($O$)**: Batas Atas Asimptotik (*Asymptotic Upper Bound*). Menjamin bahwa algoritma tidak akan berperforma lebih buruk dari batas tertentu untuk $N$ yang cukup besar.
  $$\exists c > 0, n_0 > 0 \quad \text{s.t.} \quad \forall n \ge n_0, \quad 0 \le f(n) \le c \cdot g(n)$$
* **Big-Omega ($\Omega$)**: Batas Bawah Asimptotik (*Asymptotic Lower Bound*).
  $$\exists c > 0, n_0 > 0 \quad \text{s.t.} \quad \forall n \ge n_0, \quad 0 \le c \cdot g(n) \le f(n)$$
* **Big-Theta ($\Theta$)**: Batas Ketat Asimptotik (*Tight Bound*). Terpenuhi jika dan hanya jika $f(n) = O(g(n))$ dan $f(n) = \Omega(g(n))$.
  $$\exists c_1, c_2 > 0, n_0 > 0 \quad \text{s.t.} \quad \forall n \ge n_0, \quad c_1 \cdot g(n) \le f(n) \le c_2 \cdot g(n)$$

Dalam konteks wawancara teknis dan LeetCode, ketika pewawancara menanyakan *"Berapa time complexity kodenya?"*, mereka hampir selalu menanyakan **Big-O pada skenario terburuk (*worst-case scenario*)**.

---

### 5. Cara Kerja Mekanistis (How It Works Under the Hood)

#### A. Mekanisme Penghitungan Operasi CPU
CPU mengeksekusi instruksi per siklus jam (*clock cycle*). Operasi dasar seperti assignment variabel (`x = 1`), operasi aritmatika primitif (`a + b`), dan perbandingan logika (`a > b`) dipetakan menjadi instruksi assembly berbiaya rendah ($O(1)$).

Namun, kompleksitas waktu tidak menghitung instruksi per siklus secara mikro, melainkan menghitung **berapa kali operasi dominan dieksekusi sebagai fungsi dari $N$**:

```python
def contoh_mekanisme(n):
    total = 0               # 1 operasi (konstanta, diabaikan)
    for i in range(n):      # Loop dieksekusi n kali
        for j in range(n):  # Loop dieksekusi n kali
            total += (i * j)# Operasi dominan: dieksekusi n * n kali
    return total
```
Kompleksitas: $f(N) = N^2 + 1 \implies O(N^2)$. Konstanta dieliminasi karena saat $N \to \infty$, kontribusi nilai skalar tidak signifikan terhadap kurva pertumbuhan.

#### B. Mekanisme Pemakaian Memori (*Call Stack* & *Heap*)
*Space Complexity* dihitung dari:
1. **Auxiliary Space**: Memori tambahan di luar input asli.
2. **Input Space**: Memori yang dialokasikan untuk menyimpan data input.

Pada algoritma rekursif, setiap pemanggilan fungsi mendorong satu *stack frame* ke dalam *Call Stack* arsitektur memori sistem:

```python
def rekursi_faktorial(n):
    if n <= 1:
        return 1
    return n * rekursi_faktorial(n - 1)
```
Meskipun tidak ada struktur data tambahan (array/map) yang diinisialisasi, fungsi di atas menggunakan $O(N)$ Auxiliary Space karena sistem mengalokasikan $N$ frame pada *Call Stack* hingga *base case* tercapai. Jika $N$ melebihi limit rekursi sistem (default Python umumnya 1000), program akan melempar `RecursionError: maximum recursion depth exceeded`.

---

### 6. Diagram ASCII: Klasifikasi Laju Pertumbuhan & Peta Kendala (*Constraint Map*)

```text
Operasi
  ^
  |                                                O(N!)     O(2^N)
  |                                                  |        |
  |                                                  |       /  O(N^2)
  |                                                  |      /  /
  |                                                  |     /  /   O(N log N)
  |                                                  |    /  /   /
  |                                                  |   /  /   /   O(N)
  |                                                  |  /  /   /   /
  |                                                  | /  /   /   /
  |                                                  |/  /   /   /
  |--------------------------------------------------+--/---/---/---> O(log N)
  |--------------------------------------------------+----------------> O(1)
  +--------------------------------------------------------------------> N (Input Size)

========================================================================================
                      LEETCODE CONSTRAINT DECISION MATRIX
========================================================================================
Ukuran Input (N)       Kompleksitas Target Maksimum     Algoritma / Teknik Tipikal
----------------------------------------------------------------------------------------
N <= 10 - 12           O(N!) atau O(N^2 * 2^N)          Permutasi, TSP, Bitmask DP
N <= 20 - 25           O(2^N)                           Backtracking, Subsets, Meet-in-the-middle
N <= 100               O(N^4) atau O(N^3)               Floyd-Warshall, Basic DP 3D
N <= 500 - 1.000       O(N^2)                           Nested loops, Dynamic Programming 2D
N <= 10.000            O(N * sqrt(N))                   Sqrt Decomposition, Mo's Algorithm
N <= 100.000 - 10^6    O(N log N) atau O(N)             Sorting, Binary Search, Two Pointers,
                                                        Sliding Window, Prefix Sums, Hash Map
N >= 10^9              O(log N) atau O(1)               Binary Search, Math (Modulo Pow), Matrix Exponentiation
========================================================================================
```

---

### 7. Contoh Minimalis / Simple Example

#### Masalah: Mencari apakah ada elemen duplikat dalam array ($N \le 10^5$).

**Implementasi Buruk ($O(N^2)$ Time, $O(1)$ Space) - Berpotensi TLE:**
```python
def contains_duplicate_slow(nums: list[int]) -> bool:
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] == nums[j]:
                return True
    return False
```
*Analisis Operasi*: Untuk $N = 10^5$, loop dalam dieksekusi sebanyak $\frac{N(N-1)}{2} \approx 5 \times 10^9$ operasi. Melebihi batas aman $10^8$ operasi $\implies$ **TLE**.

**Implementasi Optimal ($O(N)$ Time, $O(N)$ Space) - Trade-off Ruang untuk Waktu:**
```python
def contains_duplicate_fast(nums: list[int]) -> bool:
    seen = set()
    for num in nums:
        if num in seen: # Hash table lookup: rata-rata O(1)
            return True
        seen.add(num)
    return False
```
*Analisis Operasi*: Loop berjalan maksimal $N$ kali. Operasi pengecekan dan penyisipan *Hash Set* bekerja secara amortized $O(1)$. Total operasi: $10^5$. Waktu eksekusi: $\approx 0.02$ detik $\implies$ **ACCEPTED**.

---

### 8. Kasus Nyata LeetCode / Practical Example

#### LeetCode 1: Two Sum
**Deskripsi**: Diberikan array integer `nums` dan integer `target`, kembalikan indeks dua angka yang jika dijumlahkan menghasilkan `target`.  
**Batasan (*Constraints*)**:
* $2 \le \text{nums.length} \le 10^4$
* $-10^9 \le \text{nums}[i] \le 10^9$
* $-10^9 \le \text{target} \le 10^9$
* Hanya ada satu solusi valid.

**Evaluasi Teknis**:
Berdasarkan matriks batasan, $N = 10^4$. Jika kita menggunakan $O(N^2)$, jumlah operasi adalah $10^8$. Nilai ini berada di ambang batas toleransi CPU; pada bahasa interpretasi lambat seperti Python, pendekatan ini berisiko besar menghasilkan TLE atau paling tidak berada pada persentil runtime terbawah. Target arsitektur kode haruslah $O(N)$ atau $O(N \log N)$.

#### Solusi Optimal dengan One-Pass Hash Table ($O(N)$ Time, $O(N)$ Space):

```python
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        # Hash map untuk menyimpan {nilai: indeks}
        lookup_table: dict[int, int] = {}
        
        for current_idx, current_val in enumerate(nums):
            complement = target - current_val
            
            # Verifikasi keberadaan komplemen dalam map
            if complement in lookup_table:
                return [lookup_table[complement], current_idx]
            
            # Simpan indeks dari nilai saat ini
            lookup_table[current_val] = current_idx
            
        return []
```

#### Amortized Analysis pada Kasus Ini:
Penggunaan *Hash Map* bergantung pada resolusi tabrakan (*collision resolution*). Pada kondisi ideal, pencarian dan penyisipan beroperasi pada $O(1)$. 
Namun, skenario terburuk (*worst-case*) terjadi bila terjadi tabrakan hash secara luas (semua elemen memiliki nilai modulus hash yang sama), membuat operasi lookup terdegradasi ke $O(N)$, sehingga total waktu menjadi $O(N^2)$. 

Engine runtime modern (seperti *SipHash* pada Python atau *Robin Hood hashing*) secara statistik meminimalkan probabilitas ini hingga mendekati nol, memungkinkan kita menganggap operasionalnya konstan $O(1)$ ter-amortisasi.

---

### 9. Trade-offs & Batasan Desain

Dalam pemrograman kompetitif dan sistem produksi, optimasi waktu hampir selalu berbenturan dengan konsumsi memori:

| Pendekatan Algoritmik | Time Complexity | Space Complexity | Konsekuensi & Keterbatasan |
|---|---|---|---|
| **Brute Force (Nested Loops)** | $O(N^2)$ | $O(1)$ | Tidak butuh alokasi memori tambahan, tetapi komputasi membengkak drastis saat input membesar. |
| **Two Pointers (In-place sort)** | $O(N \log N)$ | $O(1)$ atau $O(\log N)$ | Memodifikasi struktur array asli. Tidak bisa digunakan jika urutan indeks asli diperlukan (kecuali jika array dipasangkan dengan indeks aslinya). |
| **Hash Table Lookup** | $O(N)$ | $O(N)$ | Eksekusi tercepat. Konsumsi memori tinggi karena overhead pointer dan bucket hash table. |
| **Bit Manipulation (Bitset)** | $O(N)$ | $O(1)$ / $O(U/64)$ | Memori sangat padat (menggunakan bit integer), tetapi terbatas hanya jika rentang nilai input diskrit dan kecil ($U \le 10^7$). |

---

### 10. Panduan Implementasi & Anti-patterns

#### Anti-Pattern 1: Operasi Bersembunyi dalam Loop (*Hidden Complexity Trap*)
Banyak programmer pemula terjebak memanggil metode bawaan (*built-in*) di dalam loop tanpa menyadari kompleksitas internalnya:

```python
# SANGAT BURUK: Kompleksitas O(N^2)
def inefficient_check(nums: list[int]) -> bool:
    for x in nums:
        # Operator 'in' pada Python List adalah linear search O(N)!
        if nums.count(x) > 1: # O(N) di dalam loop O(N) = O(N^2)
            return True
    return False
```

#### Anti-Pattern 2: String Concatenation Invariant
String pada bahasa seperti Java, Python, dan C# bersifat *immutable*. Melakukan konkatenasi string di dalam loop menghasilkan alokasi array baru di setiap iterasi:

```python
# BURUK: O(N^2) Time karena reallokasi buffer string berukuran terus membesar
s = ""
for char in char_list:
    s += char 

# OPTIMAL: O(N) Time menggunakan list buffer lalu di-join
s = "".join(char_list)
```

#### Best Practice Checklist:
1. Pastikan operasi pencarian dalam loop menggunakan struktur data dengan lookup $O(1)$ (`set`, `dict`) alih-alih `list`.
2. Lakukan alokasi ukuran array di awal (*pre-allocation*) jika ukuran diketahui untuk mencegah penataan ulang buffer dinamis secara berkala.

---

### 11. Edge Cases & Penanganan Kegagalan

Setiap kali mengonstruksi solusi dari analisis batasan input, periksa kondisi batas ekstrem ini:

1. **Input Minimum / Batas Bawah**: 
   * Array kosong (`len == 0`) atau elemen tunggal (`len == 1`).
   * Pointer `null` atau `None`.
2. **Nilai Integer Ekstrem**:
   * Masalah dengan penjumlahan: $a + b$ dapat menyebabkan **32-bit signed integer overflow** jika nilainya melebihi $2^{31} - 1$ ($2.147.483.647$) di C/C++ dan Java.
   * *Mitigasi*: Gunakan tipe data `long long` (C++) atau `long` (Java). Python menangani *arbitrary-precision integers* secara dinamis, tetapi tetap membebani waktu komputasi.
3. **Komponen Graf/Array Tidak Terhubung**:
   * Graf asiklik terputus (*disconnected component*), node dengan *self-loop*, atau siklus tak berujung yang menyebabkan *infinite call stack*.

---

### 12. Optimalisasi Performa & Resource

#### Memahami Amortized Expansion pada Dinamic Array (Vector / List)
Struktur data seperti `std::vector` (C++) atau `list` (Python) mengalokasikan kapasitas berbasis faktor pengganda (umumnya 1.5x atau 2x).

* Saat kapasitas penuh tercapai pada elemen ke-$K$, sistem mengalokasikan array baru berukuran $2K$, menyalin seluruh $K$ elemen lama, lalu menambahkan elemen baru.
* Waktu penyisipan pada elemen ke-$K$: $O(K)$.
* Namun, $K$ operasi penyisipan berikutnya bernilai $O(1)$.
* **Amortized Time Complexity**:
  $$\frac{\sum \text{Cost}}{N} = \frac{N + (1 + 2 + 4 + 8 + \dots + N)}{N} < \frac{3N}{N} = O(1)$$
* **Optimalisasi Praktis**: Jika ukuran akhir dapat diestimasi, gunakan `vector.reserve(N)` (C++) untuk menghindari *reallocation penalty* berulang.

---

### 13. Aspek Keamanan / Ketahanan Sistem (Robustness)

Dalam algoritma pencarian berbasis rekursi (misal: *Depth First Search* pada graf matriks berukuran $1000 \times 1000$):
* **Potensi Bahaya**: Kerusakan eksekusi program melalui **Stack Overflow**.
* **Pencegahan**:
  1. Ubah rekursi implisit menjadi iterasi eksplisit menggunakan struktur data `Stack` pada memori *Heap*. Ruang memori *Heap* dibatasi oleh RAM sistem (gigabytes), sementara *Stack* dibatasi oleh limit OS (seringkali hanya 8MB).
  2. Di Python, tingkatkan limit rekursi secara eksplisit hanya bila terpaksa:
     ```python
     import sys
     sys.setrecursionlimit(200000)
     ```

---

### 14. Testing & Verifikasi

Untuk memverifikasi kebenaran kompleksitas asimptotik kode Anda secara empiris sebelum submit:

#### Teknik Generator Kasus Ekstrem (Stress Testing Harness)
Uji ketahanan runtime kode Anda secara lokal menggunakan script pengujian mandiri:

```python
import time
import random

def verify_runtime_scaling():
    test_sizes = [10_000, 100_000, 1_000_000]
    
    for size in test_sizes:
        # Inisialisasi data sintetis kasus terburuk
        synthetic_input = [random.randint(1, 10**9) for _ in range(size)]
        
        start_time = time.perf_counter()
        
        # Eksekusi algoritma target
        _ = sorted(synthetic_input) # Simulasi O(N log N)
        
        duration = time.perf_counter() - start_time
        print(f"Size: {size:<8} | Time Elapsed: {duration:.6f} seconds")

if __name__ == "__main__":
    verify_runtime_scaling()
```
*Evaluasi*: Jika peningkatan input 10x ($10^4 \to 10^5$) meningkatkan durasi waktu $\approx 10-14$ kali lipat, kode terverifikasi $O(N \log N)$. Jika melompat $\approx 100$ kali lipat, kode Anda secara empiris terbukti mengalami regresi ke $O(N^2)$.

---

### 15. Integrasi Ekosistem LeetCode

Saat menginterpretasikan feedback platform:
* **Runtime Percentile Variance**: Hasil metrik runtime LeetCode (misal: "Faster than 85%") memiliki varians tinggi karena *load sharing* server virtualisasi. Jangan mengandalkan persentil untuk validasi asimptotik; validasikan melalui penghitungan langkah algoritma teoritis.
* **I/O Overhead**: Pada C++, gunakan sinkronisasi I/O cepat di konstruktor class untuk memotong overhead standar:
  ```cpp
  static const auto fast_io = []() {
      std::ios_base::sync_with_stdio(false);
      std::cin.tie(NULL);
      return 0;
  }();
  ```

---

### 16. FAQ Teknis

**Q: Apa perbedaan mendasar antara $O(N)$ dan $\Theta(N)$ jika keduanya sering dipertukarkan?**  
*A: $O(N)$ adalah payung batas atas. Algoritma dengan kompleksitas konstan $O(1)$ secara matematis valid dikatakan $O(N)$ karena tidak pernah melebihi laju linier. Sebaliknya, $\Theta(N)$ mengikat secara mutlak dari atas dan bawah; algoritma hanya $\Theta(N)$ jika laju pertumbuhannya persis sebanding dengan $N$.*

**Q: Mengapa algoritma $O(N \log N)$ saya menghasilkan TLE pada $N = 10^5$?**  
*A: Periksa konstanta tersembunyi ($c$). Kompleksitas $O(c \cdot N \log N)$ dengan $c$ besar (misalnya membuat copy array di tiap level rekursi, alokasi objek berat, atau hashing string berukuran panjang) akan melampaui batasan operasi CPU aktual.*

---

### 17. Checklist Produksi LeetCode (Pre-Submission Checklist)

Sebelum menekan tombol **Submit**, lakukan verifikasi berikut:
- [ ] **Constraint Check**: Berapa nilai maksimum input ($N$)? Apakah kompleksitas algoritma saya memenuhi syarat *Decision Matrix*?
- [ ] **Worst Case Scenarios**: Apakah ada skenario nilai input yang membuat algoritma terdegradasi (misalnya: Quick Sort tanpa pivot acak pada array terurut)?
- [ ] **Data Types**: Apakah ada potensi overflow penjumlahan/perkalian integer?
- [ ] **Variable State Reset**: Apakah ada variabel global/class-level yang mempertahankan state antar pemanggilan fungsi test case berbeda?
- [ ] **Space Complexity Stack**: Berapa kedalaman pemanggilan rekursi maksimum? Apakah berpotensi memicu MLE/Stack Overflow?

---

### 18. Latihan Praktik Terpandu

#### Masalah: Maximum Subarray (Kadane's Algorithm)
Diberikan array integer `nums`, temukan *subarray* contiguous yang memiliki jumlah terbesar dan kembalikan nilai penjumlahannya.

*Batasan Input*: $N \le 10^5$, $-10^4 \le \text{nums}[i] \le 10^4$.

#### Tahap 1: Evaluasi Batasan
$N = 10^5 \implies$ Pendekatan Brute Force $O(N^2)$ (memeriksa semua pasangan $(i, j)$) akan membutuhkan sekitar $10^{10} / 2 = 5 \times 10^9$ operasi $\implies$ **Pasti TLE**. Target kita harus $O(N)$ atau $O(N \log N)$.

#### Tahap 2: Dekonstruksi Pola Pikir Algoritmik (Kadane's Dynamic Programming)
Pada setiap indeks $i$, kita dihadapkan pada dua pilihan:
1. Memperpanjang subarray sebelumnya yang berakhir di $i-1$ dengan menambahkan elemen $nums[i]$.
2. Memulai subarray baru yang hanya beranggotakan $nums[i]$.

#### Tahap 3: Implementasi Solusi Optimal $O(N)$ Time, $O(1)$ Space
```python
class Solution:
    def maxSubArray(self, nums: list[int]) -> int:
        # Inisialisasi dengan elemen pertama untuk menangani kasus semua bilangan negatif
        current_sum = nums[0]
        max_sum = nums[0]
        
        # Iterasi mulai dari elemen kedua: O(N) linear scan
        for i in range(1, len(nums)):
            x = nums[i]
            # Formulasi transisi state:
            # current_sum[i] = max(x, current_sum[i-1] + x)
            current_sum = max(x, current_sum + x)
            
            # Update perolehan global
            if current_sum > max_sum:
                max_sum = current_sum
                
        return max_sum
```

---

### 19. Lembar Contekan / Referensi Cepat

```text
========================================================================================
                      BIG-O TIME COMPLEXITY CHEAT SHEET
========================================================================================
Notasi        Nama              Operasi untuk N = 10^6         Contoh Operasi
----------------------------------------------------------------------------------------
O(1)          Konstan           1 operasi                      Hash table lookup / array index
O(log N)      Logaritmik        ~20 operasi                    Binary Search, Balanced BST lookup
O(N)          Linier            1.000.000 operasi              Single loop scan, Counting sort
O(N log N)    Linearitmik       ~20.000.000 operasi            Merge Sort, Heap Sort, Quick Sort (avg)
O(N^2)        Kuadratik         10^12 operasi (TLE)            Nested loops, Bubble Sort
O(2^N)        Eksponensial      10^300000 operasi (TLE fatal)  Subset generation, recursion tanpa memo
O(N!)         Faktorial         Overflow tak hingga (TLE)      Permutasi murni (N > 12 = TLE)
========================================================================================
```

---

### 20. Rekomendasi Modul Berikutnya & Bacaan Lanjutan
* **Modul Berikutnya**: **Bab 01 - Modul 02: Primitive Data Structures, In-Place Array Transformations, dan Teknik Two-Pointers**.
* **Bacaan Lanjutan Terverifikasi**:
  * *Introduction to Algorithms (CLRS)*: Bab 3 (Growth of Functions) & Bab 17 (Amortized Analysis).
  * *Competitive Programmer's Handbook* (Antti Laaksonen): Bab 2 (Time Complexity).
  * Profiler Dokumentasi Resmi Python: `cProfile` dan `timeit` internal engine tracing.