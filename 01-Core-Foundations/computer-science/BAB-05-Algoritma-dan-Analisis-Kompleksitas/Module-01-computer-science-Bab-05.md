# Kurikulum Computer Science: Core Foundations
## Bab 05 — Modul 01: Algoritma & Analisis Kompleksitas

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: CS-CF-05-01
* **Nama Jalur (Track)**: Computer Science Core Foundations
* **Kategori**: 01-Core-Foundations
* **Tingkat Kompleksitas**: Intermediate to Advanced
* **Prasyarat**: Matematika Diskrit (Induksi Matematika, Teori Himpunan, Notasi Asimtotik Dasar, Deret Geometri), Pemrograman Dasar (C/C++ atau Python), Konsep Arsitektur Komputer Dasar (Model Von Neumann, Memori Hirarkis).
* **Estimasi Beban Kerja**: 10–12 jam pembelajaran mandiri, studi kasus, dan analisis matematis.
* **Target Pembaca**: Mahasiswa Ilmu Komputer tingkat menengah, Rekayasawan Perangkat Lunak (Software Engineers) yang ingin memperkuat fundamental evaluasi kinerja sistem, dan Arsitek Sistem yang mendesain algoritma berskala besar.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis** efisiensi algoritma secara independen terhadap perangkat keras menggunakan model komputasi teoritis (Random Access Machine / RAM model).
2. **Membuktikan** batas asimtotik ketat (*tight bound*) suatu fungsi menggunakan definisi formal kalkulus dan teori himpunan ($O, \Omega, \Theta, o, \omega$).
3. **Menyelesaikan** relasi rekursif (*recurrence relations*) kompleks menggunakan metode Substitusi (*Substitution Method*), Pohon Rekursi (*Recursion Tree*), dan Teorema Master (*Akra-Bazzi Theorem* / *Master Theorem*).
4. **Mengevaluasi** performa amortisasi (*amortized performance*) struktur data mutabel dinamis dengan metode Agregat, Akuntansi (*Accounting Method*), dan Fungsi Potensial Fisik (*Physicist’s Potential Method*).
5. **Mengukur dan Memvalidasi** kompleksitas ruang memori (*Auxiliary vs Total Space Complexity*) termasuk konsumsi *call stack* dan alokasi *heap*.
6. **Mengidentifikasi** *algorithmic bottlenecks* pada sistem produksi nyata serta membedakan antara kompleksitas teoritis (*big-O*) dan batas performa praktis (efek *cache locality*, instruksi SIMD, dan *branch prediction*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [Analisis Kompleksitas Algoritma]
                                          │
       ┌──────────────────────────────────┼──────────────────────────────────┐
       ▼                                  ▼                                  ▼
[Model Komputasi]               [Notasi Asimtotik]               [Metode Analisis]
 ├── RAM Model                   ├── Upper Bound: O, o            ├── Analisis Iteratif
 ├── Primitive Operations        ├── Tight Bound: Θ               ├── Analisis Rekursif
 └── Invariant Program           └── Lower Bound: Ω, ω            │    ├── Master Theorem
                                                                  │    ├── Recursion Tree
                                                                  │    └── Akra-Bazzi
                                                                  └── Analisis Teramortisasi
                                                                       ├── Agregat
                                                                       ├── Akuntansi
                                                                       └── Metode Potensial (Φ)
```

### Relasi Antar Konsep
* **Model RAM** menyediakan abstraksi di mana setiap operasi primitif (aritmatika, penugasan, pengalamatan memori) membutuhkan waktu $O(1)$.
* **Notasi Asimtotik** mendeskripsikan perilaku batas (*limiting behavior*) fungsi waktu/ruang dari model RAM ketika ukuran input $n \to \infty$.
* **Analisis Rekursif** dan **Analisis Teramortisasi** merupakan instrumen kalkulasi lanjut untuk algoritma yang membagi masalah (Divide-and-Conquer) atau struktur data dengan latensi tak merata antar-operasi.

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1. **Skalabilitas Sistem dan Kegagalan Non-Linier**: Algoritma dengan kompleksitas $O(n^2)$ bekerja mulus pada data pengujian lokal ($n = 1.000 \to 10^6$ operasi, < 1 ms), namun dapat menyebabkan *service outage* fatal di lingkungan produksi ($n = 10^6 \to 10^{12}$ operasi, butuh ~16 menit komputasi intensif pada CPU 1 GHz).
2. **Hardware Scaling Inadequacy**: Hukum Moore telah melambat. Kita tidak lagi dapat mengandalkan peningkatan *clock speed* CPU untuk menutupi desain algoritma yang buruk. Mengurangi kompleksitas dari $O(n^2)$ ke $O(n \log n)$ melampaui optimasi perangkat keras puluhan tahun.
3. **Efisiensi Finansial dan Cloud Economics**: Di era komputasi awan, biaya infrastruktur berbanding lurus dengan siklus CPU ($vCPU/hour$) dan memori ($GB-hour$). Optimasi algoritma memangkas biaya operasional skala enterprise secara langsung.
4. **Pencegahan Vektor Serangan Keamanan (Algorithmic Complexity Attacks)**: Algoritma dengan *worst-case* yang buruk (misalnya ReDoS pada Regular Expressions atau Hash Flooding Attack pada Hash Map $O(n)$) dapat dieksploitasi oleh penyerang untuk melancarkan *Denial of Service* (DoS).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Model Random Access Machine (RAM)
Model teoretis yang mengasumsikan:
* Instruksi dieksekusi secara sekuensial satu per satu.
* Operasi dasar: aritmatika (`+`, `-`, `*`, `/`), kontrol alur (`branch`, `call`, `return`), dan akses memori membutuhkan satu satuan unit waktu konstan.
* Memori bersifat tak terbatas dan akses ke alamat mana pun membutuhkan waktu yang setara (mengabaikan hirarki cache L1/L2/L3 untuk kesederhanaan analisis matematis).

### 2. Definisi Formal Notasi Asimtotik

Misalkan $f(n)$ dan $g(n)$ adalah fungsi non-negatif dari himpunan bilangan bulat positif ke bilangan real positif:

#### A. Notasi Big-O (Asymptotic Upper Bound)
$$O(g(n)) = \{ f(n) : \exists c > 0 \text{ dan } n_0 > 0 \text{ sehingga } 0 \le f(n) \le c \cdot g(n) \text{ untuk semua } n \ge n_0 \}$$
*Makna*: Menjamin bahwa laju pertumbuhan $f(n)$ tidak akan pernah melampaui $g(n)$ dikalikan konstanta $c$, untuk ukuran data input yang cukup besar ($n \ge n_0$).

#### B. Notasi Big-Omega (Asymptotic Lower Bound)
$$\Omega(g(n)) = \{ f(n) : \exists c > 0 \text{ dan } n_0 > 0 \text{ sehingga } 0 \le c \cdot g(n) \le f(n) \text{ untuk semua } n \ge n_0 \}$$
*Makna*: Menjamin batas bawah laju pertumbuhan algoritma.

#### C. Notasi Big-Theta (Asymptotically Tight Bound)
$$\Theta(g(n)) = \{ f(n) : \exists c_1 > 0, c_2 > 0, \text{ dan } n_0 > 0 \text{ sehingga } 0 \le c_1 \cdot g(n) \le f(n) \le c_2 \cdot g(n) \text{ untuk semua } n \ge n_0 \}$$
*Teorema*: $f(n) = \Theta(g(n)) \iff f(n) = O(g(n)) \land f(n) = \Omega(g(n))$.

#### D. Notasi Little-o dan Little-omega (Strict Bounds)
* **Little-o**: Menunjukkan batas atas yang *tidak ketat secara asimtotik*.
  $$o(g(n)) = \{ f(n) : \forall c > 0, \exists n_0 > 0 \text{ sehingga } 0 \le f(n) < c \cdot g(n) \text{ untuk semua } n \ge n_0 \}$$
  Ekuivalen dengan limit: $\lim_{n \to \infty} \frac{f(n)}{g(n)} = 0$.
* **Little-omega**: Menunjukkan batas bawah yang *tidak ketat secara asimtotik*.
  $$\omega(g(n)) = \{ f(n) : \forall c > 0, \exists n_0 > 0 \text{ sehingga } 0 \le c \cdot g(n) < f(n) \text{ untuk semua } n \ge n_0 \}$$
  Ekuivalen dengan limit: $\lim_{n \to \infty} \frac{f(n)}{g(n)} = \infty$.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Metode Analisis Algoritma Rekursif

#### Teorema Master (Master Theorem)
Diterapkan untuk relasi perulangan dengan bentuk:
$$T(n) = a \cdot T\left(\frac{n}{b}\right) + f(n)$$
Di mana $a \ge 1$, $b > 1$, dan $f(n)$ adalah fungsi waktu pemrosesan pada tahap *divide* dan *combine*. Bandingkan $f(n)$ dengan $n^{\log_b a}$:

1. **Kasus 1**: Jika $f(n) = O(n^{\log_b a - \epsilon})$ untuk suatu konstanta $\epsilon > 0$, maka:
   $$T(n) = \Theta(n^{\log_b a})$$
2. **Kasus 2**: Jika $f(n) = \Theta(n^{\log_b a} \log^k n)$ di mana $k \ge 0$, maka:
   $$T(n) = \Theta(n^{\log_b a} \log^{k+1} n)$$
3. **Kasus 3**: Jika $f(n) = \Omega(n^{\log_b a + \epsilon})$ untuk suatu konstanta $\epsilon > 0$, dan memenuhi **kondisi keteraturan** (*regularity condition*): $a \cdot f(n/b) \le c \cdot f(n)$ untuk suatu konstanta $c < 1$ dan $n$ besar, maka:
   $$T(n) = \Theta(f(n))$$

### 2. Metode Analisis Teramortisasi (Amortized Analysis)
Digunakan ketika operasi individual membutuhkan biaya mahal, namun frekuensinya sangat rendah sehingga rata-rata biaya per operasi dalam jangka panjang tetap rendah.

* **Metode Agregat**: Menghitung batas atas total biaya urutan $k$ operasi, $T(k)$. Biaya teramortisasi per operasi adalah $\frac{T(k)}{k}$.
* **Metode Akuntansi (Tebungan)**: Menetapkan biaya buatan (*amortized cost*) $\hat{c}_i$ pada tiap operasi. Operasi murah dikenai biaya lebih tinggi dari aktualnya ($c_i$); selisihnya disimpan sebagai saldo kredit untuk mendanai operasi mahal di masa depan. Saldo kredit tidak boleh bernilai negatif: $\sum_{i=1}^k \hat{c}_i - \sum_{i=1}^k c_i \ge 0$.
* **Metode Potensial (Fisika)**: Mendefinisikan fungsi potensial $\Phi$ yang memetakan keadaan struktur data $D$ ke bilangan real: $\Phi(D)$.
  Biaya teramortisasi $\hat{c}_i$ didefinisikan sebagai:
  $$\hat{c}_i = c_i + \Phi(D_i) - \Phi(D_{i-1})$$
  Jika $\Phi(D_n) \ge \Phi(D_0)$, maka total biaya amortisasi merupakan batas atas valid dari total biaya aktual:
  $$\sum_{i=1}^n \hat{c}_i = \sum_{i=1}^n c_i + \Phi(D_n) - \Phi(D_0) \ge \sum_{i=1}^n c_i$$

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Spektrum Laju Pertumbuhan Asimtotik

```
Waktu / Langkah (T)
  ▲
  │                                                      O(2^n)
  │                                                   │  [Eksponensial]
  │                                              O(n!)│
  │                                                │  │
  │                                         O(n^2) │  │
  │                                            │   │  │
  │                                            │   │  │
  │                                   O(n log n)   │  │
  │                                      │     │   │  │
  │                                 O(n) │     │   │  │  [Linear]
  │                                  │   │     │   │  │
  │                          O(log n)│   │     │   │  │  [Logaritmik]
  │                             │    │   │     │   │  │
  │                    O(1)─────┴────┴───┴─────┴───┴──┴── [Konstan]
  └──────────────────────────────────────────────────────────────►
  0                                                            Ukuran Input (n)
```

### Pohon Rekursi (Recursion Tree) untuk $T(n) = 2T(n/2) + cn$

```
Level 0:                 cn                            = cn
                       /    \
Level 1:           c(n/2)   c(n/2)                     = cn
                   /   \     /   \
Level 2:       c(n/4) c(n/4) c(n/4) c(n/4)             = cn
                / \    / \   / \    / \
                ...    ...   ...    ...
Level log₂n:  T(1)   T(1)   T(1)   ...  T(1)           = c * 2^(log₂n) * 1 = cn
              └───┬────────────────────────┘
                 n node dasar
───────────────────────────────────────────────────────────────────────────
Total Biaya:  Sum_{i=0}^{log₂ n} (cn) = cn * (log₂ n + 1) = Θ(n log n)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

### Analisis Formal Pembuktian Notasi Asimtotik

Buktikan secara formal bahwa $f(n) = 3n^2 + 5n + 7$ adalah $\Theta(n^2)$.

#### Bukti Matematis:
Berdasarkan definisi $\Theta$, kita harus menemukan konstanta positif $c_1, c_2,$ dan $n_0$ sehingga:
$$c_1 n^2 \le 3n^2 + 5n + 7 \le c_2 n^2 \quad \forall n \ge n_0$$

1. **Mencari Upper Bound ($c_2$ dan $n_0^{(1)}$)**:
   Untuk $n \ge 1$:
   $$5n \le 5n^2$$
   $$7 \le 7n^2$$
   Maka:
   $$3n^2 + 5n + 7 \le 3n^2 + 5n^2 + 7n^2 = 15n^2$$
   Diperoleh $c_2 = 15$ untuk $n \ge 1$.

2. **Mencari Lower Bound ($c_1$ dan $n_0^{(2)}$)**:
   Untuk $n \ge 1$, karena semua suku bernilai positif ($5n > 0$ dan $7 > 0$):
   $$3n^2 + 5n + 7 \ge 3n^2$$
   Diperoleh $c_1 = 3$ untuk $n \ge 1$.

3. **Konklusi**:
   Pilih $c_1 = 3$, $c_2 = 15$, dan $n_0 = \max(1, 1) = 1$.
   Terbukti bahwa:
   $$3n^2 \le 3n^2 + 5n + 7 \le 15n^2 \quad \forall n \ge 1$$
   Maka $3n^2 + 5n + 7 \in \Theta(n^2)$. $\blacksquare$

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi analisis teramortisasi pada struktur data **Vektor Dinamis (Dynamic Array / std::vector)** menggunakan C++20. Kita akan membedah proses resizing dengan pemodelan fungsi potensial.

```cpp
#include <iostream>
#include <memory>
#include <chrono>
#include <stdexcept>

template <typename T>
class ResizableArray {
private:
    T* data;
    size_t capacity_;
    size_t size_;
    size_t total_reallocations;
    size_t total_element_copies;

    void resize(size_t new_capacity) {
        T* new_data = new T[new_capacity];
        for (size_t i = 0; i < size_; ++i) {
            new_data[i] = std::move(data[i]);
            total_element_copies++;
        }
        delete[] data;
        data = new_data;
        capacity_ = new_capacity;
        total_reallocations++;
    }

public:
    ResizableArray() 
        : data(new T[1]), capacity_(1), size_(0), 
          total_reallocations(0), total_element_copies(0) {}

    ~ResizableArray() {
        delete[] data;
    }

    // Push back dengan strategi penggandaan geometric (2x)
    void push_back(const T& value) {
        if (size_ == capacity_) {
            // Biaya resize: O(N) amortized ke O(1)
            resize(capacity_ * 2);
        }
        data[size_++] = value;
    }

    size_t size() const { return size_; }
    size_t capacity() const { return capacity_; }
    size_t get_copies() const { return total_element_copies; }
    size_t get_reallocs() const { return total_reallocations; }
};

int main() {
    constexpr size_t N = 1'000'000;
    ResizableArray<int> arr;

    auto start = std::chrono::high_resolution_clock::now();

    for (size_t i = 0; i < N; ++i) {
        arr.push_back(static_cast<int>(i));
    }

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> elapsed = end - start;

    std::cout << "Penyisipan Elemen: " << N << "\n";
    std::cout << "Kapasitas Akhir : " << arr.capacity() << "\n";
    std::cout << "Total Realloc   : " << arr.get_reallocs() << "\n";
    std::cout << "Total Kopi      : " << arr.get_copies() << "\n";
    std::cout << "Rata-rata Kopi/Item: " 
              << static_cast<double>(arr.get_copies()) / N << "\n";
    std::cout << "Waktu Eksekusi  : " << elapsed.count() << " ms\n";

    return 0;
}
```

### Analisis Bukti Potensial Fisik:
Definisikan fungsi potensial $\Phi(D_i) = 2 \cdot \text{size}_i - \text{capacity}_i$.
* Awalnya: $\text{size}_0 = 0, \text{capacity}_0 = 0 \implies \Phi(D_0) = 0$.
* Sesaat sebelum ekspansi: $\text{size}_{i-1} = \text{capacity}_{i-1} \implies \Phi(D_{i-1}) = \text{capacity}_{i-1}$.
* Operasi pengisian tanpa resize:
  $$\hat{c}_i = c_i + \Phi(D_i) - \Phi(D_{i-1}) = 1 + (2(\text{size}_{i-1} + 1) - \text{capacity}) - (2\cdot\text{size}_{i-1} - \text{capacity}) = 1 + 2 = 3$$
* Operasi pengisian dengan ekspansi (misal kapasitas berlipat ganda dari $k$ ke $2k$):
  Biaya aktual $c_i = k + 1$ ($k$ salinan + 1 penambahan item baru).
  $$\Phi(D_i) = 2(k + 1) - 2k = 2$$
  $$\Phi(D_{i-1}) = 2k - k = k$$
  $$\hat{c}_i = c_i + \Phi(D_i) - \Phi(D_{i-1}) = (k + 1) + 2 - k = 3$$
Karena untuk seluruh kasus $\hat{c}_i \le 3$, biaya per operasi adalah terbukti amortisasi $O(1)$.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pendekatan Teoritis ($O(N)$) | Realitas Hardware Modern | Catatan Rekayasa Sistem |
| :--- | :--- | :--- | :--- |
| **Akses Memori** | Mengasumsikan latensi uniform (1 unit RAM). | Hirarki Cache (L1: ~1ns, L2: ~4ns, L3: ~10ns, DRAM: ~60ns). | Algoritma cache-oblivious atau berbasis contiguous array jauh melampaui node-based pointers (seperti `std::list`). |
| **Ukuran Konstanta ($c$)** | Diabaikan dalam notasi asimtotik ($O(c \cdot n) = O(n)$). | Nilai $c$ yang besar merusak latensi praktis. | Algoritma $O(n \log n)$ dengan konstanta kecil lebih cepat dari $O(n)$ dengan konstanta masif untuk $n < 10^7$. |
| **Trade-off Ruang vs Waktu** | Mengorbankan ruang untuk waktu atau sebaliknya. | Tekanan memori memicu *swapping* disk (Thrashing). | Menggunakan Hash Table $O(1)$ yang memakan memori berlebih dapat menyebabkan *Page Fault* yang berakibat latensi melompat drastis. |
| **Karakteristik Input** | Worst-Case vs Best-Case. | Skewness data aktual di lingkungan produksi. | Algoritma QuickSort ($O(n^2)$ worst-case) secara empiris lebih dipilih daripada HeapSort ($O(n \log n)$ tight) karena *cache locality*. |

---

## SEKSI 11 — BEST PRACTICES

1. **Selalu Analisis Tiga Kondisi Ekstrem**:
   * *Best-case*: Sering kali tidak relevan secara arsitektural, kecuali untuk *early-exit bailout*.
   * *Average-case*: Bergantung pada model distribusi input riil (gunakan model probabilistik formal).
   * *Worst-case*: Standar baku toleransi SLA (*Service Level Agreement*) rekayasa perangkat lunak mission-critical.
2. **Definisikan Notasi Ruang Pembantu (*Auxiliary Space*) vs Total Space**:
   Pastikan Anda memisahkan memori input dengan memori tambahan yang dialokasikan oleh algoritma. Perhatikan alokasi *Call Stack Frame* pada pemanggilan fungsi rekursif.
3. **Waspadai Struktur Data Dinamis Berbasis Node**:
   Hindari struktur pointer bersarang (`std::list`, Pohon Biner Naif) di jalur kritis latensi (*critical hot-path*) karena masalah fragmentasi memori dan destruksi performa CPU *cache prefetching*.
4. **Validasi Asimtotik Empiris**:
   Lakukan *curve fitting* pada data uji nyata menggunakan skala Log-Log. Kemiringan (*slope*) garis regresi log-log menunjukkan derajat polinomial dari kompleksitas algoritma:
   $$\log(T(n)) = k \cdot \log(n) + \log(c) \implies \text{Kemiringan } k \text{ adalah orde eksponen algoritma.}$$

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Menyamakan Kasus Rata-Rata (Average Case) dengan Analisis Teramortisasi (Amortized)**:
   * *Kesalahan*: Menganggap amortisasi melibatkan probabilitas input acak.
   * *Koreksi*: Analisis teramortisasi menjamin batas atas waktu *terburuk* rata-rata untuk serangkaian operasi terurut, **tanpa** melibatkan asumsi probabilistik apapun terhadap input.
2. **Mengabaikan Alokasi Call Stack Rekursif**:
   * *Kesalahan*: Menganggap ruang algoritma DFS (Depth-First Search) atau QuickSort adalah $O(1)$ karena tidak mengalokasikan array baru secara eksplisit.
   * *Koreksi*: Kedalaman tumpukan pemanggilan rekursif (*call stack frames*) mengonsumsi ruang $O(d)$, di mana $d$ adalah kedalaman rekursi maksimal.
3. **Mengabaikan Biaya Operasi Primitif yang Tersembunyi**:
   * *Kesalahan*: Menganggap pemanggilan slicing string/array `arr[i:j]` pada Python adalah $O(1)$.
   * *Koreksi*: Slicing pada Python melakukan deep copying memori dengan kompleksitas $O(j - i)$. Periksa selalu implementasi internal runtime.
4. **Salah Menerapkan Kasus Teorema Master**:
   * *Kesalahan*: Menggunakan Master Theorem pada kasus non-polinomial gap, contohnya $T(n) = 2T(n/2) + n \log n$.
   * *Koreksi*: Rasio $f(n) / n^{\log_b a} = \log n$, yang bukan merupakan perbedaan polinomial $n^\epsilon$. Harus diselesaikan dengan varian Extended Master Theorem atau Recursion Tree.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Soal 1: Analisis Master Theorem (Tingkat Menengah)
Tentukan batas asimtotik ketat ($\Theta$) dari persamaan rekursif berikut menggunakan Master Theorem. Tunjukkan kasus mana yang berlaku dan buktikan keteraturannya jika relevan:
$$T(n) = 4T\left(\frac{n}{2}\right) + n^2 \sqrt{n}$$

### Soal 2: Desain Model Amortisasi Struktur Data (Tingkat Lanjut)
Sebuah struktur data Antrean Berbasis Dua Tumpukan (*Queue implemented via two Stacks: $S_{\text{in}}$ dan $S_{\text{out}}$*) memiliki operasi:
* `enqueue(x)`: memasukkan elemen ke $S_{\text{in}}$.
* `dequeue()`: jika $S_{\text{out}}$ kosong, memindahkan seluruh isi $S_{\text{in}}$ ke $S_{\text{out}}$ secara LIFO, lalu melakukan `pop` dari $S_{\text{out}}$.

**Tugas Anda**: Buktikan menggunakan **Metode Potensial (Potential Method)** bahwa biaya teramortisasi dari operasi `dequeue()` adalah $O(1)$ untuk rangkaian $n$ operasi sembarang berurutan.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. Jika sebuah algoritma memiliki fungsi waktu $T(n) = n^2 + 1000n$, manakah dari pernyataan berikut yang **paling benar** secara matematis?
   * A. $T(n) \in O(n)$
   * B. $T(n) \in o(n^2)$
   * C. $T(n) \in \omega(n)$
   * D. $T(n) \in \Theta(n^3)$
   * **Kunci & Rasional**: **C**. Nilai $\lim_{n \to \infty} \frac{n^2 + 1000n}{n} = \infty$, yang merupakan definisi presisi dari $\omega(n)$.

2. Manakah relasi hierarki yang benar untuk batas asimtotik ketika $n \to \infty$?
   * A. $O(1) < O(\log \log n) < O(\log n) < O(\sqrt{n}) < O(n) < O(n \log n) < O(n^2)$
   * B. $O(1) < O(\log n) < O(\log \log n) < O(n) < O(\sqrt{n})$
   * C. $O(n \log n) < O(\sqrt{n}) < O(n^2)$
   * D. $O(\log n!) = O(n^2)$
   * **Kunci & Rasional**: **A**. Logaritma iterated/ganda bertumbuh jauh lebih lambat dari logaritma standar, dan $\sqrt{n} = n^{0.5}$ berada di antara $\log n$ dan $n^1$.

3. Misalkan fungsi running time sebuah algoritma adalah $T(n) = 8T(n/4) + n^2$. Berapakah nilai kompleksitas asimtotiknya?
   * A. $\Theta(n^{\log_4 8}) = \Theta(n^{1.5})$
   * B. $\Theta(n^2)$
   * C. $\Theta(n^2 \log n)$
   * D. $\Theta(n^3)$
   * **Kunci & Rasional**: **B**. Di sini $a=8, b=4$. Maka $n^{\log_b a} = n^{\log_4 8} = n^{1.5}$. Fungsi $f(n) = n^2 = n^{1.5 + 0.5}$. Karena $\epsilon = 0.5 > 0$, Kasus 3 Teorema Master berlaku: $a \cdot f(n/b) = 8(n/4)^2 = 8(n^2 / 16) = \frac{1}{2} n^2 \le c f(n)$ dengan $c = 1/2 < 1$. Jadi hasilnya adalah $\Theta(f(n)) = \Theta(n^2)$.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C.** (2022). *Introduction to Algorithms* (4th ed.). MIT Press. (Bab 3: Characterizing Running Times; Bab 4: Divide-and-Conquer; Bab 17: Amortized Analysis).
2. **Sedgewick, R., & Wayne, K.** (2011). *Algorithms* (4th ed.). Addison-Wesley Professional. (Bab 1.4: Analysis of Algorithms).
3. **Knuth, D. E.** (1997). *The Art of Computer Programming, Volume 1: Fundamental Algorithms* (3rd ed.). Addison-Wesley. (Mathematical Analysis of Algorithms).
4. **Akra, M., & Bazzi, L.** (1998). *On the solution of linear recurrence relations*. Computational Optimization and Applications, 10(2), 195-210.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
+────────────────────+─────────────────────────────+──────────────────────────────────────+
| Notasi / Konsep    | Definisi Formal Singkat     | Interpretasi Praktis                 |
+────────────────────+─────────────────────────────+──────────────────────────────────────+
| O(g(n))            | f(n) <= c * g(n)            | "Paling lambat", batas atas terjamin |
| Ω(g(n))            | f(n) >= c * g(n)            | "Paling cepat", batas bawah terjamin |
| Θ(g(n))            | c1*g(n) <= f(n) <= c2*g(n)  | Laju pertumbuhan presisi (tight)     |
| o(g(n))            | lim [f(n) / g(n)] = 0       | Batas atas strictly strictly dominan |
| Amortized Analysis | (Total Biaya n Ops) / n     | Menjamin rata-rata terburuk beruntun |
| Master Theorem     | T(n) = aT(n/b) + f(n)       | Solusi rekursif tanpa pohon eksplisit|
+────────────────────+─────────────────────────────+──────────────────────────────────────+
```

Inti analisis kompleksitas terletak pada evaluasi ketat bagaimana kebutuhan memori dan komputasi bertambah seiring bertumbuhnya input tanpa terikat pada variabilitas arsitektur perangkat keras tertentu.

---

## SEKSI 17 — GLOSARIUM

* **Asymptotics (Asimtotika)**: Studi mengenai perilaku fungsi matematika ketika argumennya mendekati nilai tak terhingga ($\infty$).
* **Auxiliary Space**: Jumlah memori sementara tambahan yang digunakan oleh suatu algoritma di luar representasi memori data input itu sendiri.
* **Cache Locality**: Prinsip di mana memori yang baru diakses atau yang berdekatan secara fisik cenderung diakses kembali dalam waktu dekat oleh CPU cache.
* **Potential Function ($\Phi$)**: Fungsi skalar pemetaan dari struktur data ke bilangan real yang merepresentasikan energi/kapasitas cadangan yang disimpan oleh struktur tersebut.
* **RAM Model**: Abstraksi mesin universal deterministik serial tanpa mekanisme konkurensi, di mana seluruh instruksi atomik memiliki biaya eksekusi seragam.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Pedoman Pengajaran**: Hindari pengajaran algoritma hanya melalui pseudo-code tanpa pembuktian limit formal. Mahasiswa sering kali bingung antara Worst-Case Analysis dan Big-O; tekankan bahwa Big-O dapat digunakan untuk menyatakan fungsi batas atas pada *best-case*, *average-case*, maupun *worst-case*.
* **Area Sering Keliru**: Mahasiswa sering terjebak menghafal kasus Master Theorem tanpa memahami kondisi keteraturan (*regularity condition*). Demonstrasikan contoh kasus gagal seperti $T(n) = 2T(n/2) + n \sin(n)$.
* **Rubrik Penilaian Latihan Amortisasi**:
  * Poin Penuh: Mendefinisikan status $\Phi(D_0) = 0$, membuktikan $\Phi(D_i) \ge 0$, dan menunjukkan secara aljabar bahwa $\hat{c}_i = c_i + \Delta\Phi_i = O(1)$ untuk semua kondisi transisi.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (2024-03-29):
  * Rilis inisial kurikulum dengan integrasi pembuktian formal matematika kalkulus dan representasi C++ modern (std::chrono & memory movement).
  * Penambahan bab spesifik analisis teramortisasi metode potensial.
  * Standardisasi format 20 seksi dokumen pedagogis teknis GEMINI.md.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CS-CF-04-03: Manajemen Memori Virtual & Arsitektur Subsistem OS`
* **Modul Berikutnya**: `CS-CF-05-02: Struktur Data Linear Tingkat Lanjut & Algoritma Manipulasi Pointer`
* **Indeks Jalur Pembelajaran**: [Daftar Lengkap Materi Kategori 01-Core-Foundations](./README.md)