## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** DSA-01-09-01
* **Nama Modul:** Algoritma String Lanjutan & Primitif Komputasi Geometri
* **Kategori:** 01-Core-Foundations
* **Tingkat Kesulitan:** Advanced
* **Prasyarat Teknis:**
  * Pemahaman mendalam tentang Array, Hashing, dan Pointer.
  * Analisis Asimptotik Kompleksitas Waktu & Ruang ($\mathcal{O}$, $\Omega$, $\Theta$).
  * Aljabar Linier Dasar (Vektor 2D, Determinan Matriks $2 \times 2$).
  * Aritmatika Modular (Operasi modulo, invers modular dasar).
* **Estimasi Beban Belajar:** 240 Menit (Teori: 90 Menit, Analisis Kode: 60 Menit, Latihan Terpandu: 90 Menit).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Mengkonstruksi** fungsi prefix ($\pi$) pada algoritma Knuth-Morris-Pratt (KMP) dalam kompleksitas waktu deterministik $\mathcal{O}(m)$.
2. **Mengimplementasikan** pencarian pola string linear $\mathcal{O}(n + m)$ menggunakan KMP dengan eliminasi *backtracking* pada pointer teks.
3. **Mendesain** skema *Polynomial Rolling Hash* berbasis aritmatika modular pada algoritma Rabin-Karp dengan probabilitas tabrakan hash (*spurious hits*) yang minimal.
4. **Menerapkan** operasi *Cross Product* 2D untuk mengevaluasi orientasi titik (*clockwise*, *counter-clockwise*, *collinear*) tanpa ketergantungan pada fungsi trigonometri floating-point.
5. **Menyelesaikan** permasalahan *Convex Hull* 2D menggunakan algoritma Graham Scan / Monotone Chain dengan kompleksitas waktu $\mathcal{O}(n \log n)$.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              [Pemrosesan Domain Khusus]
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
 [Algoritma String]                                           [Komputasi Geometri 2D]
        |                                                                   |
   +----+--------------------+                                        +----+--------------------+
   |                         |                                        |                         |
[State/Automata]      [Algebraic Hashing]                      [Primitif Vektor]      [Struktur Konveks]
   |                         |                                        |                         |
[KMP: pi-Array]       [Rabin-Karp]                             [Cross Product]         [Convex Hull]
- Preprocessing O(m)  - Polynomial Hash                         - Orientasi 3 Titik     - Graham Scan
- Search O(n)         - O(1) Sliding Window                     - Turn Detection        - Andrew's Monotone
- Zero Backtracking   - Modulo Arithmetic                      - Determinant Area        Chain O(n log n)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pencarian string naif ($\mathcal{O}(n \times m)$) dan penalaran geometri berbasis trigonometri presisi mengambang (*floating-point trigonometry*) adalah dua sumber kegagalan terbesar dalam sistem komputasi performa tinggi:

1. **Efisiensi Mesin Pencari & Bioinformatika:**
   Analisis sekuens genomik (DNA/RNA) memproses miliaran karakter ($n \approx 3 \times 10^9$). Algoritma kuadratik akan gagal total karena eksekusi memakan waktu berhari-hari. KMP dan Rabin-Karp menjamin pemrosesan linear $\mathcal{O}(n)$, memungkinkan analisis perbandingan genomik skala besar secara efisien.

2. **Deteksi Duplikasi & Plagiarisme:**
   Rabin-Karp memanfaatkan struktur aljabar *rolling hash*, memungkinkan pemindaian substring multi-pola (*multi-pattern matching*) secara simultan dalam satu lintasan linear.

3. **Integritas Numerik Sistem Spasial (GIS, Game Engine, Robotika):**
   Penggunaan fungsi `atan2()` atau pembagian floating-point rentan terhadap *floating-point roundoff errors* ($\epsilon$). Satu kesalahan pembulatan pada kalkulasi persimpangan garis dapat menyebabkan robot otonom menabrak rintangan atau *polygon clipping* pada GPU menghasilkan artefak grafis. Penggunaan *Cross Product* berbasis bilangan bulat (*integer arithmetic*) memberikan determinisme 100% pada evaluasi orientasi spasial.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Knuth-Morris-Pratt (KMP) Algorithm
KMP adalah algoritma pencocokan string linear yang memanfaatkan simetri internal pola (*pattern self-similarity*). KMP menghindari kembalinya pointer teks (*backtracking*) dengan melakukan komputasi awal terhadap fungsi prefix (dikenal sebagai array $\pi$ atau *Longest Proper Prefix which is also Suffix* - LPS).

$$\pi[i] = \max \{ k \mid k < i+1 \land P[0 \dots k-1] = P[i-(k-1) \dots i] \}$$

### 2. Rabin-Karp Algorithm
Rabin-Karp adalah algoritma pencarian string berbasis *probabilistic hashing*. Substring sepanjang $m$ dipetakan ke representasi nilai skalar menggunakan representasi polinomial basis $B$ modulo bilangan prima besar $M$:

$$H(S[i \dots i+m-1]) = \left( \sum_{j=0}^{m-1} S[i+j] \cdot B^{m-1-j} \right) \pmod M$$

Perpindahan jendela (*sliding window*) dari indeks $i$ ke $i+1$ dihitung dalam $\mathcal{O}(1)$:

$$H_{i+1} = \left( (H_i - S[i] \cdot B^{m-1}) \cdot B + S[i+m] \right) \pmod M$$

### 3. Primitif Geometri: 2D Cross Product (Perkalian Silang)
Perkalian silang dua vektor 2D $\vec{PQ}$ dan $\vec{PR}$ dihitung melalui determinan matriks $2 \times 2$:

$$\vec{PQ} \times \vec{PR} = (Q_x - P_x)(R_y - P_y) - (Q_y - P_y)(R_x - P_x)$$

* **Nilai $> 0$:** Belok Kiri (*Counter-Clockwise* / CCW).
* **Nilai $< 0$:** Belok Kanan (*Clockwise* / CW).
* **Nilai $= 0$:** Kolinier (*Collinear* / Segaris lurus).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Workflow Algoritma KMP

```
[Inisialisasi pi[0] = 0, j = 0, i = 1]
                 |
  +------------->+
  |              |
  |      [Apakah i < m?] ---- TIDAK ---> [Array pi Selesai Dibuat]
  |              | YA
  |    [P[i] == P[j] ?]
  |      |          |
  |     YA        TIDAK
  |      |          |
  |  [pi[i] = j+1]  +---> [j > 0 ?] --- YA ---> [j = pi[j-1]] (Fallback)
  |  [i++, j++]             | TIDAK
  |      |            [pi[i] = 0, i++]
  +------+                  |
         +------------------+
```

1. **Fase Preprocessing Pola ($P$):**
   * Buat array $\pi$ berukuran $m$. Tetapkan $\pi[0] = 0$.
   * Iterasi pointer $i$ dari $1$ ke $m-1$. Gunakan pointer $j$ untuk melacak panjang prefix terpanjang yang cocok.
   * Jika $P[i] == P[j]$, inkrementasi $j$ dan catat $\pi[i] = j$.
   * Jika mismatch dan $j > 0$, geser $j$ mundur menggunakan $j = \pi[j-1]$ secara rekursif hingga cocok atau $j = 0$.
   * Jika mismatch dan $j == 0$, tetapkan $\pi[i] = 0$.

2. **Fase Pencarian pada Teks ($T$):**
   * Iterasi pointer teks $k$ dari $0$ ke $n-1$, pointer pola $l$ dari $0$ ke $m-1$.
   * Jika $T[k] == P[l]$, gerakkan kedua pointer maju ($k{+}{+}, l{+}{+}$).
   * Jika $l == m$, substring ditemukan pada indeks $k - m$. Transisikan state pola: $l = \pi[l-1]$.
   * Jika mismatch ($T[k] \neq P[l]$): jika $l > 0$, geser $l = \pi[l-1]$; jika $l == 0$, inkrementasi $k$. Pointer $k$ **tidak pernah mundur**.

---

### Workflow Orientasi Geometri & Convex Hull (Graham Scan / Monotone Chain)

```
[Daftar Titik P] ---> [Urutkan P berdasarkan X, lalu Y]
                               |
              +----------------+----------------+
              |                                 |
     [Bangun Lower Hull]               [Bangun Upper Hull]
              |                                 |
   Periksa Orientasi 3 Titik:        Periksa Orientasi 3 Titik:
   CrossProduct(p[-2], p[-1], pt)    CrossProduct(p[-2], p[-1], pt)
         <= 0 ? (Bukan CCW)                <= 0 ? (Bukan CCW)
              | YA                              | YA
       Pop titik terakhir                Pop titik terakhir
              |                                 |
              +----------------+----------------+
                               |
           [Gabungkan Lower Hull & Upper Hull]
```

1. **Sorting:** Urutkan himpunan titik $S$ secara leksikografis berdasarkan koordinat $x$, kemudian koordinat $y$. Kompleksitas: $\mathcal{O}(n \log n)$.
2. **Lower Hull Construction:** Iterasi titik dari kiri ke kanan. Tambahkan titik ke dalam stack. Selama ukuran stack $\ge 2$ dan orientasi dari dua titik teratas stack ke titik baru tidak membentuk belokan kiri murni (Cross Product $\le 0$), buang titik teratas (*pop*).
3. **Upper Hull Construction:** Iterasi titik dari kanan ke kiri dengan aturan stack yang identik.
4. **Merge:** Gabungkan kedua hull dan hilangkan elemen duplikat pada batas sambungan.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. State Tracking KMP saat Terjadi Mismatch

Misalkan Pola $P = \text{"ABABC"}$, Teks $T = \text{"ABABABC"}$.

```
Teks T:    A  B  A  B  A  B  C
Pola P:    A  B  A  B  C
Index:     0  1  2  3  4
Match:    [v  v  v  v] x  --> Mismatch di P[4] ('C') vs T[4] ('A')

Nilai Array pi untuk P:
i:     0  1  2  3  4
P[i]:  A  B  A  B  C
pi[i]: 0  0  1  2  0

Aksi:
Mismatch terjadi di index pola 4.
j bergeser ke pi[4 - 1] = pi[3] = 2.
Alih-alih mengulang dari T[1], teks pointer tetap di T[4], pola bergeser:

Teks T:    A  B  A  B  A  B  C
Pola P:          A  B  A  B  C  (Pola bergeser, index pola kini j = 2)
Match:          [v  v] v  v  v  --> Sukses cocok penuh!
```

---

### 2. Evaluasi 2D Cross Product (Aturan Tangan Kanan 2D)

Misalkan titik $P(1, 1)$, $Q(4, 2)$, dan $R(2, 4)$.
Vektor $\vec{PQ} = (4-1, 2-1) = (3, 1)$
Vektor $\vec{PR} = (2-1, 4-1) = (1, 3)$

```
   Y ^
   5 |
   4 |         * R(2,4)
   3 |        /
   2 |       /       * Q(4,2)
   1 |      * P(1,1)/
   0 +------------------------> X
     0  1  2  3  4  5

Determinan:
| PQ_x   PR_x |   | 3   1 |
| PQ_y   PR_y | = | 1   3 | = (3 * 3) - (1 * 1) = 9 - 1 = +8 (> 0)

Hasil > 0: Belok Kiri (Counter-Clockwise / CCW).
Titik R berada di sebelah kiri lintasan garis berarah PQ.
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Penentuan Orientasi 3 Titik

Diberikan tiga titik pada bidang Kartesius:
* $A = (0, 0)$
* $B = (4, 4)$
* $C = (2, 2)$ (Kasus Degenerasi: Kolinier)
* $D = (4, 1)$ (Kasus Belok Kanan)

```python
def orientation(p1, p2, p3):
    # Cross Product dari (p2 - p1) x (p3 - p1)
    val = (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
    if val == 0:
        return "KOLINIER"
    elif val > 0:
        return "COUNTER-CLOCKWISE (KIRI)"
    else:
        return "CLOCKWISE (KANAN)"

# Evaluasi Titik Kolinier
print(orientation((0, 0), (4, 4), (2, 2)))  # Output: KOLINIER

# Evaluasi Belok Kanan
print(orientation((0, 0), (4, 4), (4, 1)))  # Output: CLOCKWISE (KANAN)
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi level produksi dalam Python 3 yang mencakup:
1. **Engine Pencari KMP** dengan penanganan edge cases komprehensif.
2. **Andrew’s Monotone Chain 2D Convex Hull** dengan proteksi integer overflow dan immutability tipe data.

```python
from typing import List, Tuple

# =====================================================================
# 1. KNUTH-MORRIS-PRATT (KMP) STRING MATCHER
# =====================================================================

def compute_lps_array(pattern: str) -> List[int]:
    """
    Menghitung tabel Longest Proper Prefix which is also Suffix (pi).
    Kompleksitas Waktu: O(m)
    Kompleksitas Ruang: O(m)
    """
    m = len(pattern)
    lps = [0] * m
    length = 0  # Panjang prefix sebelumnya yang cocok
    i = 1

    while i < m:
        if pattern[i] == pattern[length]:
            length += 1
            lps[i] = length
            i += 1
        else:
            if length != 0:
                # Geser kembali ke prefix sebelumnya, jangan naikkan i
                length = lps[length - 1]
            else:
                lps[i] = 0
                i += 1
    return lps

def kmp_search(text: str, pattern: str) -> List[int]:
    """
    Mencari semua kemunculan pattern di dalam text.
    Mengembalikan list berisi indeks awal kemunculan pola.
    Kompleksitas Waktu: O(n + m)
    Kompleksitas Ruang: O(m)
    """
    if not pattern or not text:
        return []

    n = len(text)
    m = len(pattern)
    if m > n:
        return []

    lps = compute_lps_array(pattern)
    matches: List[int] = []
    
    i = 0  # Pointer untuk text
    j = 0  # Pointer untuk pattern

    while i < n:
        if pattern[j] == text[i]:
            i += 1
            j += 1

        if j == m:
            matches.append(i - j)
            j = lps[j - 1]  # Reset j menggunakan lps untuk mencari match berikutnya
        elif i < n and pattern[j] != text[i]:
            if j != 0:
                j = lps[j - 1]
            else:
                i += 1

    return matches


# =====================================================================
# 2. COMPUTATIONAL GEOMETRY: CONVEX HULL (ANDREW'S MONOTONE CHAIN)
# =====================================================================

Point = Tuple[int, int]

def cross_product(o: Point, a: Point, b: Point) -> int:
    """
    Menghitung nilai perkalian silang 2D dari vektor OA dan OB.
    Nilai > 0 : Belokan CCW (kiri)
    Nilai < 0 : Belokan CW (kanan)
    Nilai = 0 : Kolinier
    """
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

def convex_hull_monotone_chain(points: List[Point]) -> List[Point]:
    """
    Membangun Convex Hull dari sekumpulan titik 2D.
    Kompleksitas Waktu: O(n log n) karena pemilahan (sorting).
    Kompleksitas Ruang: O(n)
    """
    # Menghapus duplikasi titik dan mengurutkan secara leksikografis (x, lalu y)
    unique_points = sorted(list(set(points)))
    n = len(unique_points)

    if n <= 1:
        return unique_points

    # Membangun Lower Hull
    lower: List[Point] = []
    for p in unique_points:
        while len(lower) >= 2 and cross_product(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Membangun Upper Hull
    upper: List[Point] = []
    for p in reversed(unique_points):
        while len(upper) >= 2 and cross_product(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Titik terakhir pada lower dan upper sama dengan titik pertama pada segmen lawan.
    # Buang elemen penutup untuk menghindari duplikasi.
    return lower[:-1] + upper[:-1]


# =====================================================================
# INTEGRATION TESTING & DEMONSTRASI EKSEKUSI
# =====================================================================
if __name__ == "__main__":
    # Test String Algorithm: KMP
    sample_text = "BACADABACABABACABACAB"
    sample_pat = "ABACAB"
    found_indices = kmp_search(sample_text, sample_pat)
    print(f"[KMP Matching] Teks: {sample_text}")
    print(f"[KMP Matching] Pola: {sample_pat}")
    print(f"[KMP Matching] Pola ditemukan pada indeks: {found_indices}")

    # Test Geometry Algorithm: Convex Hull
    raw_points: List[Point] = [
        (0, 3), (2, 2), (1, 1), (2, 1), (3, 0),
        (0, 0), (3, 3), (2, -1), (2, 4), (1, 4)
    ]
    hull = convex_hull_monotone_chain(raw_points)
    print(f"\n[Geometry] Jumlah Titik Input: {len(raw_points)}")
    print(f"[Geometry] Titik-titik Boundary Convex Hull: {hull}")
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

### Tabel Perbandingan Algoritma Pencarian String

| Algoritma | Waktu Preprocessing | Waktu Pencarian (Worst) | Waktu Pencarian (Avg) | Ruang Tambahan | Kebutuhan Memori Pointer Backtracking |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Naif** | $\mathcal{O}(1)$ | $\mathcal{O}(n \cdot m)$ | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ | Ya (Pointer teks mundur) |
| **KMP** | $\mathcal{O}(m)$ | $\mathcal{O}(n + m)$ | $\mathcal{O}(n)$ | $\mathcal{O}(m)$ | **Tidak** (Streaming friendly) |
| **Rabin-Karp** | $\mathcal{O}(m)$ | $\mathcal{O}(n \cdot m)$ | $\mathcal{O}(n + m)$ | $\mathcal{O}(1)$ | **Tidak** (Sangat efisien untuk multi-pattern) |
| **Boyer-Moore**| $\mathcal{O}(m + |\Sigma|)$ | $\mathcal{O}(n \cdot m)$ | $\mathcal{O}(n / m)$ | $\mathcal{O}(m + |\Sigma|)$ | Ya (Sangat cepat pada alfabet besar) |

### Trade-offs: Floating Point vs Integer Arithmetic pada Komputasi Geometri

1. **Floating-point (`float64`):**
   * *Kelebihan:* Mampu memproses rentang koordinat kontinu secara langsung.
   * *Bahaya:* Operasi `(a * b) - (c * d)` rentan terhadap pembatalan katastropik (*catastrophic cancellation*). Determinan orientasi bisa menghasilkan nilai $\approx 10^{-16}$ yang seharusnya bernilai nol murni ($0.0$), memicu *infinite loop* atau korupsi topologi hull.
2. **Integer Arithmetic (Fixed Precision):**
   * *Kelebihan:* Orientasi deterministik absolut. Tidak ada toleransi kesalahan perbandingan epsilon ($\epsilon$).
   * *Bahaya:* Perkalian koordinat $x \cdot y$ dapat memicu *integer overflow* jika koordinat awal bertipe $64\text{-bit}$ bertanda (hasil membutuhkan representasi $128\text{-bit}$).

---

## SEKSI 11 — BEST PRACTICES

1. **Rolling Hash Protection (Double Hashing):**
   Hindari modulus tunggal $2^{64}$ (via standard `unsigned long long` overflow) pada Rabin-Karp karena rentan terhadap *hash-collision attacks* terstruktur (seperti konstruksi string Thue-Morse). Gunakan skema *Double Hashing* dengan dua modulus prima besar independen:
   
   $$M_1 = 10^9 + 7, \quad M_2 = 10^9 + 9$$

2. **Deteksi Kolinieritas Geometri yang Konsisten:**
   Pada Convex Hull, tentukan perilaku eksplisit terhadap titik-titik yang terletak sejajar pada garis batas luar (*collinear collinear points*):
   * Gunakan `cross_product(...) <= 0` jika ingin **membuang** titik kolinier (menghasilkan set titik minimum pembentuk hull).
   * Gunakan `cross_product(...) < 0` jika ingin **menyertakan** semua titik kolinier sepanjang boundary.

3. **Optimasi Buffer Stream:**
   Manfaatkan sifat KMP yang tidak membutuhkan dereferensi index teks mundur untuk memproses data dari *stream socket* atau *file pipeline* besar tanpa perlu membaca keseluruhan file ke dalam memori RAM utama.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Modulo Negatif pada Rabin-Karp:**
   Pada operasi pergeseran hash:
   
   $$\text{current\_hash} = (\text{prev\_hash} - S[i] \cdot B^{m-1}) \cdot B + S[i+m]$$
   
   Nilai $(\text{prev\_hash} - S[i] \cdot B^{m-1})$ dapat menghasilkan angka negatif. Dalam bahasa C/C++ atau Java, operator `%` menghasilkan nilai negatif. **Wajib** normalisasikan nilai sebelum modulo:
   
   $$\text{corrected\_val} = ((A - B) \pmod M + M) \pmod M$$

2. **Asumsi Convex Hull pada Titik Segaris Penuh:**
   Jika semua titik input kolinier (misalnya: $(0, 0), (1, 1), (2, 2)$), implementasi Monotone Chain yang salah dapat menghasilkan duplikasi array atau titik yang berulang tak beraturan. Selalu pastikan pemanggilan `set()` atau pembersihan leksikografis awal.

3. **Off-by-One pada LPS Array KMP:**
   Mengisi $\pi[0] = 1$ alih-alih $\pi[0] = 0$. By definition, proper prefix dari string dengan panjang 1 adalah himpunan kosong $\emptyset$, sehingga panjang maksimumnya selalu $0$.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: String Cyclical Shift Detection (Tingkat: Easy)
* **Masalah:** Diberikan dua buah string $S_1$ dan $S_2$ berukuran sama. Tentukan apakah $S_2$ merupakan hasil rotasi siklis (*cyclic shift*) dari $S_1$ dalam waktu $\mathcal{O}(n)$.
* **Input:** $S_1 = \text{"rotation"}$, $S_2 = \text{"tationro"}$
* **Output:** `True`
* **Hint:** Gandakan string pertama menjadi $S_1 + S_1$, lalu jalankan algoritma KMP untuk mencari pola $S_2$.

### Latihan 2: Validasi Poligon Konveks Sederhana (Tingkat: Medium)
* **Masalah:** Diberikan sebuah daftar $n$ titik berurutan yang merepresentasikan poligon tertutup sederhana. Buat sebuah fungsi untuk mengevaluasi apakah poligon tersebut merupakan poligon konveks (*strictly convex*).
* **Kompleksitas Target:** Waktu $\mathcal{O}(n)$, Ruang $\mathcal{O}(1)$.
* **Hint:** Tanda dari perkalian silang $\vec{P_{i}P_{i+1}} \times \vec{P_{i+1}P_{i+2}}$ harus bernilai konsisten secara ketat (semua positif atau semua negatif) untuk seluruh $i \in [0, n-1]$ dengan pengindeksan siklis modulo $n$.

### Latihan 3: Dynamic Perimeter Fence Reconstruction (Tingkat: Hard)
* **Masalah:** Diberikan sekumpulan $N$ sensor pada bidang 2D ($N \le 10^5$). Hitung keliling minimum tali elastis yang dapat membungkus seluruh sensor tersebut. Jika terdapat titik baru yang ditambahkan secara dinamis, jelaskan implikasi performa dari rekonstruksi ulang full hull versus penggunaan struktur data dinamis dual-tree.
* **Output:** Nilai float perimeter dengan presisi 4 digit desimal.
* **Hint:** Bangun convex hull dengan Andrew's algorithm, kemudian iterasi perimeter dengan jarak Euclidean:
  
  $$d(A, B) = \sqrt{(A_x - B_x)^2 + (A_y - B_y)^2}$$

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Pada algoritma KMP, apa yang dihindari oleh pembangunan array $\pi$ (LPS)?**
   * A. Alokasi memori heap dinamis
   * B. Pengembalian posisi pointer indeks teks mundur (*text backtracking*)
   * C. Operasi modulo berulang
   * D. Karakter non-ASCII
   * **Jawaban:** **B**. KMP mengeliminasi kebutuhan mengulang pemeriksaan karakter teks yang sudah cocok sebelumnya.

2. **Diberikan tiga titik $A(0, 0)$, $B(5, 5)$, $C(3, 3)$. Berapa nilai cross product $\vec{AB} \times \vec{AC}$?**
   * A. $+15$
   * B. $-15$
   * C. $0$
   * D. $+9$
   * **Jawaban:** **C**. Vektor $AB = (5, 5)$ dan $AC = (3, 3)$. Determinan: $(5 \cdot 3) - (5 \cdot 3) = 0$. Titik-titik tersebut kolinier.

3. **Kapan algoritma Rabin-Karp memiliki performa terburuk $\mathcal{O}(n \cdot m)$?**
   * A. Ketika ukuran alfabet sangat besar
   * B. Ketika nilai modulo $M$ terlalu besar
   * C. Ketika terjadi tabrakan hash (*spurious hits*) yang masif pada setiap pergeseran jendela
   * D. Ketika teks dan pola sama-sama palindrom
   * **Jawaban:** **C**. Jika hash selalu cocok palsu, algoritma terpaksa melakukan komparasi string karakter-demi-karakter $\mathcal{O}(m)$ pada setiap langkah pergeseran $\mathcal{O}(n)$.

4. **Berapa batas bawah kompleksitas asimptotik waktu (*lower bound*) untuk mengonstruksi 2D Convex Hull pada model komputasi berbasis komparasi?**
   * A. $\Omega(n)$
   * B. $\Omega(n \log n)$
   * C. $\Omega(n^2)$
   * D. $\Omega(\log n)$
   * **Jawaban:** **B**. Permasalahan Convex Hull 2D dapat direduksi secara langsung dari permasalahan Sorting; oleh karena itu, batas bawahnya adalah $\Omega(n \log n)$.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Textbooks:**
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms (4th ed.)*. MIT Press. (Chapter 32: String Matching & Chapter 33: Computational Geometry).
  * de Berg, M., Cheong, O., van Kreveld, M., & Overmars, M. (2008). *Computational Geometry: Algorithms and Applications (3rd ed.)*. Springer.
* **Makalah Akademik:**
  * Knuth, D. E., Morris, J. H., & Pratt, V. R. (1977). *Fast Pattern Matching in Strings*. SIAM Journal on Computing, 6(2), 323-350.
  * Andrew, A. M. (1979). *Another efficient algorithm for convex hulls in two dimensions*. Information Processing Letters, 9(5), 216-219.
* **Standard Repositories:**
  * CP-Algorithms: `https://cp-algorithms.com/string/prefix-func.html`
  * Computational Geometry Algorithms Library (CGAL): Architecture Manual.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **KMP String Matching:** Memecahkan batasan efisiensi pencarian string melalui fungsi prefix terhitung ($\pi$). Pointer teks bergerak monotonik ke depan ($\mathcal{O}(n)$), menjadikan KMP algoritma pilihan untuk data berbasis *stream*.
2. **Rabin-Karp:** Menyediakan pendekatan probabilistik menggunakan *polynomial rolling hash*. Sangat adaptif untuk masalah pencarian multi-pola (*multi-pattern matching*) dan deteksi kesamaan dokumen skala besar.
3. **Primitif Geometri (Cross Product):** Evaluasi arah rotasi lintasan vektor pada ruang 2D diselesaikan secara eksak menggunakan determinan aljabar linier matriks $2 \times 2$. Menghindari kalkulasi trigonometri memastikan kekebalan program terhadap galat presisi pecahan.
4. **Convex Hull:** Memetakan batas terluar dari himpunan titik planar dalam $\mathcal{O}(n \log n)$ melalui penyortiran leksikografis diikuti proses eliminasi belokan cekung menggunakan struktur data stack linear.

---

## SEKSI 17 — GLOSARIUM

* **Prefix Function ($\pi$):** Array yang menyimpan panjang prefix sejati terpanjang (*longest proper prefix*) yang juga merupakan suffix untuk substring $P[0 \dots i]$.
* **Rolling Hash:** Fungsi hash yang memungkinkan komputasi nilai hash dari jendela bergeser (*sliding window*) berikutnya dalam kompleksitas waktu konstan $\mathcal{O}(1)$.
* **Spurious Hit:** Kondisi di mana nilai hash dari dua string identik, namun isi karakter sebenarnya berbeda (tabrakan fungsi hash).
* **Cross Product 2D:** Operasi pseudo-vektor determinan skalar antara dua vektor 2D yang merefleksikan besar luas jajaran genjang bertanda dan arah rotasi.
* **Convex Hull:** Poligon konveks terkecil yang melingkupi seluruh himpunan titik planar, di mana setiap segmen garis antara dua titik manapun di dalam poligon tetap berada di dalam poligon tersebut.
* **Collinear:** Kondisi di mana tiga titik atau lebih berada tepat pada satu garis lurus yang sama.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedoman Pengajaran Visual:** Jangan mulai KMP dengan kode. Mulai dengan menggambar string di papan tulis dan tunjukkan secara fisik mengapa pointer teks tidak perlu kembali ke belakang jika kita sudah mengetahui sifat prefiks pola kita sendiri.
* **Titik Kritis Mahasiswa:** Mahasiswa sering kesulitan memahami loop ganda pada Andrew's Algorithm (`while len(lower) >= 2 ...`). Tekankan bahwa meskipun ada nested-loop, total operasi `pop()` dari stack tidak akan pernah melebihi total operasi `append()` ($N$), sehingga analisis amortisasinya adalah $\mathcal{O}(n)$.
* **Eksperimen Numerik:** Tugaskan siswa untuk mengganti tipe data integer dengan `float32` pada latihan Cross Product, lalu berikan koordinat titik-titik yang sangat berdekatan ($10^{-8}$) untuk mendemonstrasikan kegagalan struktural akibat pembulatan *IEEE 754*.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Maintainer | Catatan Perubahan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 2025-01-15 | Senior Technical Curriculum Architect | Rilis kurikulum awal, implementasi algoritma KMP & Andrew's Monotone Chain terstandarisasi. |
| **v1.0.1** | 2025-02-10 | DSA Core Working Group | Penambahan analisis penanganan overflow aritmatika integer pada Cross Product. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** Bab 08: Algoritma Graf Lanjutan (Shortest Paths, Minimum Spanning Tree, Network Flow)
* **Modul Saat Ini:** Bab 09 Module 01: Algoritma String Lanjutan & Primitif Komputasi Geometri
* **Modul Berikutnya:** Bab 09 Module 02: Struktur Data Spasial Lanjutan (KD-Trees, Range Trees, Interval Trees) & Suffix Structures (Suffix Automaton/Suffix Tree).