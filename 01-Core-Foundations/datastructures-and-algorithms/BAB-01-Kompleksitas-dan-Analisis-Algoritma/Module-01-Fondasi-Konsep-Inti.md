# Data Structures & Algorithms (DSA)
## Bab 01 — Fondasi & Kompleksitas Algoritma
### Module 01 — Pengantar DSA & Analisis Kompleksitas (Big-O Notation)

---

## Metadata Modul

| Field | Value |
|---|---|
| **Course ID** | `datastructures-and-algorithms` |
| **Chapter** | 01 — Fondasi & Kompleksitas Algoritma |
| **Module** | 01 — Pengantar DSA & Analisis Kompleksitas |
| **Level** | Beginner → Intermediate |
| **Estimated Time** | 90–120 menit |
| **Prerequisites** | Pemahaman dasar pemrograman (variabel, loop, fungsi) |
| **Language** | Python 3.10+ (pseudocode-friendly) |

---

## Seksi 01 — Learning Objectives

Setelah menyelesaikan modul ini, peserta **mampu**:

```
LO-01  Menjelaskan definisi Data Structure dan Algorithm serta
       hubungan keduanya dalam pemecahan masalah komputasi.

LO-02  Membedakan kompleksitas waktu (Time Complexity) dan
       kompleksitas ruang (Space Complexity) secara konseptual.

LO-03  Membaca dan menulis notasi Big-O untuk kasus umum:
       O(1), O(log n), O(n), O(n log n), O(n²), O(2ⁿ).

LO-04  Mengidentifikasi Best Case, Average Case, dan Worst Case
       dari sebuah algoritma sederhana.

LO-05  Menerapkan analisis Big-O pada kode Python nyata dan
       membandingkan efisiensi dua solusi berbeda.

LO-06  Menghindari jebakan umum (common pitfalls) dalam
       menganalisis kompleksitas algoritma.
```

> **Bloom's Taxonomy Mapping:**
> LO-01, LO-02 → *Remember / Understand*
> LO-03, LO-04 → *Understand / Apply*
> LO-05 → *Analyze / Evaluate*
> LO-06 → *Evaluate / Create*

---

## Seksi 02 — Concept Overview (Peta Konsep)

```
┌─────────────────────────────────────────────────────────────────┐
│                    FONDASI DSA                                  │
│                                                                 │
│   ┌──────────────────┐        ┌──────────────────────────────┐  │
│   │  DATA STRUCTURE  │        │        ALGORITHM             │  │
│   │                  │        │                              │  │
│   │  Cara menyimpan  │◄──────►│  Langkah-langkah terurut     │  │
│   │  & mengorganisir │        │  untuk memecahkan masalah    │  │
│   │  data di memori  │        │  menggunakan data structure  │  │
│   └──────────────────┘        └──────────────────────────────┘  │
│            │                               │                    │
│            └───────────────┬───────────────┘                    │
│                            ▼                                    │
│              ┌─────────────────────────┐                        │
│              │   COMPLEXITY ANALYSIS   │                        │
│              │                         │                        │
│              │  Mengukur "seberapa      │                        │
│              │  efisien" solusi kita   │                        │
│              └─────────────────────────┘                        │
│                     │              │                            │
│            ┌────────┘              └────────┐                   │
│            ▼                               ▼                    │
│   ┌─────────────────┐           ┌─────────────────┐            │
│   │  TIME           │           │  SPACE          │            │
│   │  COMPLEXITY     │           │  COMPLEXITY     │            │
│   │  (Waktu eksekusi│           │  (Memori yang   │            │
│   │   vs ukuran n)  │           │   digunakan)    │            │
│   └─────────────────┘           └─────────────────┘            │
│                                                                 │
│              Diekspresikan dengan: BIG-O NOTATION               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Seksi 03 — Why (Mengapa Ini Penting?)

### 3.1 Masalah Nyata: Skala Membunuh Performa

Bayangkan dua skenario:

```
SKENARIO A — Startup kecil:
  Database: 1.000 user
  Algoritma buruk O(n²): 1.000² = 1.000.000 operasi
  Waktu: ~0.001 detik → "Tidak terasa, fine!"

SKENARIO B — Setelah viral:
  Database: 10.000.000 user
  Algoritma buruk O(n²): 10.000.000² = 100.000.000.000.000 operasi
  Waktu: ~27 JAM → Server crash, user kabur, investor marah.

  Algoritma baik O(n log n): 10.000.000 × 23 ≈ 230.000.000 operasi
  Waktu: ~0.23 detik → Semua senang.
```

### 3.2 Relevansi di Industri

| Konteks | Mengapa DSA Kritis |
|---|---|
| **Interview FAANG/Unicorn** | 80% soal teknis adalah DSA murni |
| **Backend Engineering** | Query optimization, caching strategy |
| **Machine Learning** | Gradient descent, tree traversal, graph neural network |
| **Game Development** | Pathfinding (A*), collision detection |
| **Embedded Systems** | Memori terbatas → space complexity vital |
| **Competitive Programming** | Dasar semua problem solving |

### 3.3 Mental Model Kunci

> **"Data Structure adalah WADAH, Algorithm adalah RESEP, Complexity Analysis adalah STOPWATCH + TIMBANGAN."**
>
> Anda tidak bisa memasak dengan baik tanpa tahu wadah yang tepat, resep yang benar, dan berapa lama serta bahan yang dibutuhkan.

---

## Seksi 04 — What (Definisi & Terminologi Inti)

### 4.1 Data Structure

```
DEFINISI FORMAL:
  Cara terorganisir untuk menyimpan dan mengelola data dalam
  komputer sehingga operasi tertentu dapat dilakukan secara efisien.

KATEGORI UTAMA:
  ┌─────────────────────────────────────────────────────┐
  │  LINEAR                    │  NON-LINEAR             │
  │  ─────────────────────     │  ──────────────────     │
  │  • Array                   │  • Tree                 │
  │  • Linked List             │  • Graph                │
  │  • Stack                   │  • Heap                 │
  │  • Queue                   │  • Trie                 │
  │                            │                         │
  │  HASH-BASED                │  ADVANCED               │
  │  ─────────────────────     │  ──────────────────     │
  │  • Hash Table              │  • Segment Tree         │
  │  • Hash Set                │  • Fenwick Tree         │
  │                            │  • Disjoint Set         │
  └─────────────────────────────────────────────────────┘
```

### 4.2 Algorithm

```
DEFINISI FORMAL:
  Sekumpulan instruksi terbatas, terurut, dan tidak ambigu yang
  mengubah input menjadi output yang diinginkan dalam waktu terbatas.

PROPERTI WAJIB (Knuth):
  1. FINITENESS    → Harus berhenti dalam jumlah langkah terbatas
  2. DEFINITENESS  → Setiap langkah harus jelas dan tidak ambigu
  3. INPUT         → Nol atau lebih nilai masukan
  4. OUTPUT        → Satu atau lebih nilai keluaran
  5. EFFECTIVENESS → Setiap langkah harus bisa dieksekusi
```

### 4.3 Complexity Analysis — Terminologi

| Term | Simbol | Makna |
|---|---|---|
| **Big-O** | O(f(n)) | Upper bound — Worst case (paling sering digunakan) |
| **Big-Omega** | Ω(f(n)) | Lower bound — Best case |
| **Big-Theta** | Θ(f(n)) | Tight bound — Average case (exact) |
| **Input Size** | n | Ukuran/jumlah data yang diproses |
| **Operation** | — | Satu unit kerja dasar (perbandingan, assignment, dll) |

> **Catatan Praktis:** Di industri dan interview, "Big-O" hampir selalu merujuk pada *worst-case analysis*. Kita akan fokus di sini.

---

## Seksi 05 — How (Cara Kerja & Mekanisme)

### 5.1 Cara Membaca Big-O

```
ATURAN DASAR PENYEDERHANAAN BIG-O:

  ATURAN 1 — Buang Konstanta:
    O(2n)    → O(n)
    O(500)   → O(1)
    O(3n²)   → O(n²)

  ATURAN 2 — Buang Term Non-Dominan:
    O(n² + n)      → O(n²)
    O(n + log n)   → O(n)
    O(2ⁿ + n¹⁰⁰)  → O(2ⁿ)

  ATURAN 3 — Operasi Berurutan → Tambahkan:
    step1: O(n)
    step2: O(m)
    total: O(n + m)

  ATURAN 4 — Loop Bersarang → Kalikan:
    outer loop: O(n)
    inner loop: O(m)
    total: O(n × m)
```

### 5.2 Cara Menganalisis Kode

```
LANGKAH SISTEMATIS:

  Step 1: Identifikasi ukuran input (n)
  Step 2: Hitung operasi di setiap baris
  Step 3: Fokus pada loop dan rekursi
  Step 4: Ambil term yang tumbuh paling cepat
  Step 5: Buang konstanta dan term kecil
```

### 5.3 Hierarki Kompleksitas (dari terbaik ke terburuk)

```
O(1) < O(log n) < O(n) < O(n log n) < O(n²) < O(2ⁿ) < O(n!)

TERBAIK                                                  TERBURUK
   │                                                         │
   ▼                                                         ▼
O(1)  O(log n)  O(n)  O(n log n)  O(n²)  O(2ⁿ)  O(n!)
```

---

## Seksi 06 — Diagram ASCII (Visualisasi Mendalam)

### 6.1 Kurva Pertumbuhan Big-O

```
Jumlah Operasi
     │
10⁹  │                                              ╔═══ O(n!)
     │                                           ╔══╝
     │                                        ╔══╝    ╔══ O(2ⁿ)
10⁶  │                                     ╔══╝    ╔══╝
     │                                  ╔══╝    ╔══╝
     │                            ╔═════╝    ╔══╝     ╔═ O(n²)
10³  │                       ╔════╝       ╔══╝    ╔═══╝
     │              ╔════════╝        ╔═══╝   ╔═══╝
     │    ╔══════════════════════════╝   ╔════╝        O(n log n)
10¹  │════╝·····················════════╝              O(n)
     │    ╚·················╝                          O(log n)
     │    ╚════════════════════════════════════════    O(1)
     └──────────────────────────────────────────────────────────
     0    10      100      1K      10K     100K    1M      n
```

### 6.2 Tabel Perbandingan Konkret

```
┌──────────────┬──────────────────────────────────────────────────┐
│  Kompleksitas│           Jumlah Operasi untuk n =               │
│              ├──────────┬──────────┬──────────┬─────────────────┤
│              │   n=10   │  n=100   │  n=1000  │   n=1.000.000   │
├──────────────┼──────────┼──────────┼──────────┼─────────────────┤
│    O(1)      │    1     │    1     │    1     │        1        │
│    O(log n)  │    3     │    7     │   10     │       20        │
│    O(n)      │   10     │  100     │  1.000   │    1.000.000    │
│  O(n log n)  │   33     │  664     │ 9.966    │   19.931.568    │
│    O(n²)     │  100     │ 10.000   │1.000.000 │ 10¹²  (1 triliun)│
│    O(2ⁿ)     │ 1.024    │  10³⁰   │  10³⁰¹  │   ∞ (mustahil)  │
│    O(n!)     │3.628.800 │  10¹⁵⁷  │  10²⁵⁶⁷ │   ∞ (mustahil)  │
└──────────────┴──────────┴──────────┴──────────┴─────────────────┘
```

### 6.3 Visualisasi Best / Average / Worst Case

```
CONTOH: Linear Search mencari nilai X dalam array

Array: [3, 7, 1, 9, 4, 6, 2, 8, 5]
        ↑                         ↑
      index 0                  index 8

┌─────────────────────────────────────────────────────────────┐
│  BEST CASE — Ω(1)                                           │
│  X = 3 (ada di posisi pertama)                              │
│  [3] ← KETEMU! Hanya 1 operasi.                             │
├─────────────────────────────────────────────────────────────┤
│  AVERAGE CASE — Θ(n/2) ≈ Θ(n)                               │
│  X = 4 (ada di tengah-tengah)                               │
│  [3]→[7]→[1]→[9]→[4] ← KETEMU! ~n/2 operasi.              │
├─────────────────────────────────────────────────────────────┤
│  WORST CASE — O(n)                                          │
│  X = 5 (ada di posisi terakhir) atau X tidak ada sama sekali│
│  [3]→[7]→[1]→[9]→[4]→[6]→[2]→[8]→[5] ← KETEMU! n operasi │
│  atau semua dilewati → NOT FOUND. n operasi.                │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Space Complexity — Stack Frame Rekursi

```
CONTOH: factorial(4) — Rekursif

  factorial(4)
  │
  ├── factorial(3)
  │   │
  │   ├── factorial(2)
  │   │   │
  │   │   ├── factorial(1)
  │   │   │   └── return 1
  │   │   └── return 2 × 1 = 2
  │   └── return 3 × 2 = 6
  └── return 4 × 6 = 24

CALL STACK (memori yang digunakan):
  ┌──────────────────┐  ← TOP (frame terbaru)
  │  factorial(1)    │
  ├──────────────────┤
  │  factorial(2)    │
  ├──────────────────┤
  │  factorial(3)    │
  ├──────────────────┤
  │  factorial(4)    │
  └──────────────────┘  ← BOTTOM

  Space Complexity: O(n) — n frame di stack
  (untuk factorial(n), ada n frame aktif sekaligus)
```

---

## Seksi 07 — Simple Example (Contoh Minimal)

### 7.1 O(1) — Constant Time

```python
def get_first_element(arr: list) -> int:
    """
    Mengambil elemen pertama dari array.
    Tidak peduli array punya 10 atau 10 juta elemen,
    operasi ini selalu 1 langkah.
    """
    return arr[0]  # 1 operasi, selalu

# Analisis:
# - Tidak ada loop
# - Tidak ada rekursi
# - Hanya akses index langsung
# Time Complexity : O(1)
# Space Complexity: O(1)
```

### 7.2 O(n) — Linear Time

```python
def find_max(arr: list) -> int:
    """
    Mencari nilai maksimum dalam array.
    Harus memeriksa SETIAP elemen → tumbuh linear dengan n.
    """
    max_val = arr[0]          # O(1)
    for element in arr:       # O(n) — loop n kali
        if element > max_val: # O(1) per iterasi
            max_val = element # O(1) per iterasi
    return max_val            # O(1)

# Total: O(1) + O(n) × O(1) + O(1) = O(n)
# Time Complexity : O(n)
# Space Complexity: O(1) — hanya variabel max_val
```

### 7.3 O(n²) — Quadratic Time

```python
def has_duplicate(arr: list) -> bool:
    """
    Cek apakah ada elemen duplikat.
    Versi naif: bandingkan setiap pasang elemen.
    """
    n = len(arr)
    for i in range(n):          # O(n) — loop luar
        for j in range(i+1, n): # O(n) — loop dalam
            if arr[i] == arr[j]:# O(1)
                return True
    return False

# Total: O(n) × O(n) = O(n²)
# Time Complexity : O(n²)
# Space Complexity: O(1)

# CATATAN: Ada solusi O(n) menggunakan Hash Set!
# (akan dibahas di modul Hash Table)
```

### 7.4 O(log n) — Logarithmic Time

```python
def binary_search(arr: list, target: int) -> int:
    """
    Cari target di array TERURUT.
    Setiap langkah, ruang pencarian dibagi DUA.
    """
    left, right = 0, len(arr) - 1

    while left <= right:           # Maksimal log₂(n) iterasi
        mid = (left + right) // 2  # O(1)

        if arr[mid] == target:
            return mid             # Ketemu
        elif arr[mid] < target:
            left = mid + 1         # Buang setengah kiri
        else:
            right = mid - 1        # Buang setengah kanan

    return -1  # Tidak ditemukan

# Untuk n=1.000.000: maksimal log₂(1.000.000) ≈ 20 iterasi!
# Time Complexity : O(log n)
# Space Complexity: O(1)
```

---

## Seksi 08 — Practical Example (Studi Kasus Nyata)

### 8.1 Studi Kasus: Sistem Pencarian Produk E-Commerce

**Konteks:** Platform e-commerce dengan 5 juta produk. Tim engineering harus memilih algoritma pencarian.

```python
"""
STUDI KASUS: Mencari produk berdasarkan ID
Platform: TokoPedia-like dengan 5.000.000 produk
"""

import time
import random

# ─────────────────────────────────────────────
# SOLUSI 1: Linear Search — O(n)
# ─────────────────────────────────────────────
def search_linear(products: list, target_id: int) -> dict | None:
    """
    Iterasi satu per satu dari awal hingga akhir.
    Mudah diimplementasi, tapi lambat untuk data besar.
    """
    for product in products:
        if product['id'] == target_id:
            return product
    return None

# ─────────────────────────────────────────────
# SOLUSI 2: Binary Search — O(log n)
# (Syarat: data harus terurut berdasarkan ID)
# ─────────────────────────────────────────────
def search_binary(products: list, target_id: int) -> dict | None:
    """
    Bagi dua ruang pencarian setiap iterasi.
    Jauh lebih cepat, tapi butuh data terurut.
    """
    left, right = 0, len(products) - 1

    while left <= right:
        mid = (left + right) // 2
        mid_id = products[mid]['id']

        if mid_id == target_id:
            return products[mid]
        elif mid_id < target_id:
            left = mid + 1
        else:
            right = mid - 1

    return None

# ─────────────────────────────────────────────
# SOLUSI 3: Hash Map Lookup — O(1) average
# ─────────────────────────────────────────────
def build_product_index(products: list) -> dict:
    """
    Bangun index sekali di awal: O(n) waktu, O(n) ruang.
    Setelah itu, setiap lookup hanya O(1).
    """
    return {product['id']: product for product in products}

def search_hashmap(index: dict, target_id: int) -> dict | None:
    """Lookup langsung via hash — O(1) average case."""
    return index.get(target_id)


# ─────────────────────────────────────────────
# BENCHMARK PERBANDINGAN
# ─────────────────────────────────────────────
def benchmark():
    # Simulasi 5 juta produk
    N = 5_000_000
    products = [
        {'id': i, 'name': f'Produk-{i}', 'price': random.randint(1000, 1_000_000)}
        for i in range(N)
    ]

    # Target: produk di posisi TERBURUK (akhir list)
    target_id = N - 1

    # --- Linear Search ---
    start = time.perf_counter()
    result = search_linear(products, target_id)
    linear_time = time.perf_counter() - start

    # --- Binary Search (data sudah terurut by id) ---
    start = time.perf_counter()
    result = search_binary(products, target_id)
    binary_time = time.perf_counter() - start

    # --- Hash Map (build index dulu) ---
    start = time.perf_counter()
    index = build_product_index(products)
    build_time = time.perf_counter() - start

    start = time.perf_counter()
    result = search_hashmap(index, target_id)
    hash_time = time.perf_counter() - start

    print(f"{'Algoritma':<20} {'Waktu Pencarian':>20} {'Kompleksitas':>15}")
    print("─" * 60)
    print(f"{'Linear Search':<20} {linear_time*1000:>18.2f}ms {'O(n)':>15}")
    print(f"{'Binary Search':<20} {binary_time*1000:>18.4f}ms {'O(log n)':>15}")
    print(f"{'Hash Map Build':<20} {build_time*1000:>18.2f}ms {'O(n)':>15}")
    print(f"{'Hash Map Lookup':<20} {hash_time*1000:>18.6f}ms {'O(1)':>15}")

# Output tipikal (mesin modern):
# Algoritma              Waktu Pencarian     Kompleksitas
# ────────────────────────────────────────────────────────────
# Linear Search              487.23ms              O(n)
# Binary Search                0.0021ms          O(log n)
# Hash Map Build             312.45ms              O(n)
# Hash Map Lookup              0.000089ms          O(1)
```

### 8.2 Analisis Keputusan Engineering

```
SKENARIO PENGGUNAAN:

┌─────────────────────────────────────────────────────────────────┐
│  PERTANYAAN: Kapan pakai masing-masing?                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LINEAR SEARCH → Gunakan jika:                                  │
│    ✓ Data kecil (< 1000 elemen)                                 │
│    ✓ Data tidak terurut dan tidak bisa diurutkan                │
│    ✓ Hanya butuh satu kali pencarian                            │
│    ✓ Implementasi cepat lebih penting dari performa             │
│                                                                 │
│  BINARY SEARCH → Gunakan jika:                                  │
│    ✓ Data sudah terurut (atau bisa diurutkan sekali)            │
│    ✓ Memori terbatas (O(1) space)                               │
│    ✓ Pencarian dilakukan berkali-kali                           │
│    ✓ Data jarang berubah (sorted array stabil)                  │
│                                                                 │
│  HASH MAP → Gunakan jika:                                       │
│    ✓ Pencarian sangat sering (jutaan kali/hari)                 │
│    ✓ Memori tersedia cukup (O(n) extra space OK)                │
│    ✓ Key unik dan hashable                                      │
│    ✓ Butuh O(1) lookup yang konsisten                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Seksi 09 — Trade-offs (Kompromi & Pertimbangan)

### 9.1 Time vs Space Trade-off

```
PRINSIP FUNDAMENTAL:
  "Anda hampir selalu bisa menukar waktu dengan ruang, atau sebaliknya."

CONTOH KONKRET — Fibonacci:

  ┌─────────────────────────────────────────────────────────────┐
  │  VERSI 1: Rekursif Naif                                     │
  │  Time: O(2ⁿ)  │  Space: O(n) call stack                    │
  │                                                             │
  │  def fib_naive(n):                                          │
  │      if n <= 1: return n                                    │
  │      return fib_naive(n-1) + fib_naive(n-2)                 │
  │                                                             │
  │  fib(5) menghitung fib(3) DUA KALI, fib(2) TIGA KALI!      │
  ├─────────────────────────────────────────────────────────────┤
  │  VERSI 2: Memoization (Top-Down DP)                         │
  │  Time: O(n)   │  Space: O(n) memo dict + O(n) call stack    │
  │                                                             │
  │  def fib_memo(n, memo={}):                                  │
  │      if n in memo: return memo[n]   # Pakai cache!          │
  │      if n <= 1: return n                                    │
  │      memo[n] = fib_memo(n-1, memo) + fib_memo(n-2, memo)   │
  │      return memo[n]                                         │
  │                                                             │
  │  Tukar: tambah O(n) space → hemat dari O(2ⁿ) ke O(n) time  │
  ├─────────────────────────────────────────────────────────────┤
  │  VERSI 3: Iteratif (Bottom-Up DP)                           │
  │  Time: O(n)   │  Space: O(1) — TERBAIK!                     │
  │                                                             │
  │  def fib_iterative(n):                                      │
  │      if n <= 1: return n                                    │
  │      prev, curr = 0, 1                                      │
  │      for _ in range(2, n+1):                                │
  │          prev, curr = curr, prev + curr                     │
  │      return curr                                            │
  └─────────────────────────────────────────────────────────────┘
```

### 9.2 Matriks Trade-off Algoritma Pencarian

```
┌──────────────────┬──────────┬──────────┬───────────┬──────────────┐
│   Algoritma      │   Time   │  Space   │ Perlu Sort│ Implementasi │
├──────────────────┼──────────┼──────────┼───────────┼──────────────┤
│ Linear Search    │  O(n)    │  O(1)    │    Tidak  │   Mudah      │
│ Binary Search    │ O(log n) │  O(1)    │    YA     │   Sedang     │
│ Hash Map Lookup  │  O(1)*   │  O(n)    │    Tidak  │   Sedang     │
│ Jump Search      │ O(√n)    │  O(1)    │    YA     │   Sedang     │
│ Interpolation    │ O(log log│  O(1)    │    YA     │   Sulit      │
│   Search         │    n)*   │          │           │              │
└──────────────────┴──────────┴──────────┴───────────┴──────────────┘
  * = Average case; worst case bisa lebih buruk
```

### 9.3 Theoretical vs Practical Performance

```
PERINGATAN PENTING:
  Big-O mengabaikan konstanta, tapi konstanta PENTING di dunia nyata!

  CONTOH:
    Algoritma A: 1000 × n operasi  → O(n)
    Algoritma B: 2 × n² operasi    → O(n²)

    Untuk n < 500:
      A = 1000 × 500 = 500.000 operasi
      B = 2 × 500²   = 500.000 operasi
      → SAMA!

    Untuk n < 500, Algoritma B (O(n²)) bisa lebih cepat
    karena konstanta Algoritma A sangat besar!

  PELAJARAN:
    Big-O adalah panduan, bukan kebenaran mutlak.
    Selalu BENCHMARK untuk data nyata di sistem nyata.
```

---

## Seksi 10 — Best Practices

### 10.1 Checklist Analisis Kompleksitas

```
SEBELUM MENULIS KODE:
  □ Berapa ukuran input yang diharapkan? (n = 100? 10⁶? 10⁹?)
  □ Apakah data sudah terurut atau bisa diurutkan?
  □ Berapa kali operasi ini akan dipanggil?
  □ Apakah ada batasan memori?

SAAT MENULIS KODE:
  □ Identifikasi setiap loop dan rekursi
  □ Perhatikan loop bersarang (nested loops)
  □ Waspadai operasi "tersembunyi" di library
  □ Catat asumsi tentang input

SETELAH MENULIS KODE:
  □ Hitung kompleksitas secara formal
  □ Bandingkan dengan solusi alternatif
  □ Benchmark dengan data representatif
  □ Dokumentasikan kompleksitas di docstring
```

### 10.2 Konvensi Dokumentasi Kompleksitas

```python
def merge_sort(arr: list) -> list:
    """
    Mengurutkan array menggunakan algoritma Merge Sort.

    Args:
        arr: List of comparable elements

    Returns:
        New sorted list (ascending order)

    Complexity:
        Time  : O(n log n) — all cases (best, average, worst)
        Space : O(n) — auxiliary space untuk merge

    Notes:
        - Stable sort: elemen sama mempertahankan urutan relatif
        - Tidak in-place: membutuhkan O(n) memori tambahan
        - Lebih baik dari Quick Sort untuk linked list
    """
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)
```

### 10.3 Panduan Pemilihan Algoritma Berdasarkan n

```
┌─────────────────────────────────────────────────────────────────┐
│  PANDUAN CEPAT: Berapa operasi yang "aman" per detik?           │
│  (Asumsi: ~10⁸ operasi sederhana per detik di mesin modern)     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  n ≤ 10        → O(n!) atau O(2ⁿ) masih OK                     │
│  n ≤ 20        → O(2ⁿ) masih OK                                │
│  n ≤ 500       → O(n³) masih OK                                 │
│  n ≤ 5.000     → O(n²) masih OK                                 │
│  n ≤ 10⁶       → O(n log n) atau O(n) diperlukan               │
│  n ≤ 10⁸       → O(n) diperlukan                               │
│  n > 10⁸       → O(log n) atau O(1) diperlukan                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Seksi 11 — Common Pitfalls (Jebakan Umum)

### 11.1 Pitfall #1: Mengabaikan Operasi Tersembunyi

```python
# ❌ SALAH — Terlihat O(n), sebenarnya O(n²)!
def find_duplicates_wrong(arr: list) -> list:
    duplicates = []
    for item in arr:              # O(n)
        if item not in duplicates: # O(n) ← TERSEMBUNYI! 'in' pada list = O(n)
            duplicates.append(item)
    return duplicates
# Total: O(n) × O(n) = O(n²) ← BUKAN O(n)!

# ✅ BENAR — O(n) dengan menggunakan set
def find_duplicates_correct(arr: list) -> list:
    seen = set()
    duplicates = set()
    for item in arr:              # O(n)
        if item in seen:          # O(1) ← 'in' pada set = O(1)
            duplicates.add(item)
        seen.add(item)            # O(1)
    return list(duplicates)
# Total: O(n) ✓
```

### 11.2 Pitfall #2: Salah Menghitung Rekursi

```python
# Berapa kompleksitas fungsi ini?
def mystery(n: int) -> int:
    if n <= 0:
        return 0
    return mystery(n - 1) + mystery(n - 1)  # Dua panggilan rekursif!

# ❌ Jawaban salah: "O(n) karena parameter berkurang 1 setiap kali"
# ✅ Jawaban benar: O(2ⁿ)
#
# Pohon rekursi untuk mystery(3):
#                mystery(3)
#               /           \
#         mystery(2)       mystery(2)
#         /      \          /      \
#    mystery(1) mystery(1) mystery(1) mystery(1)
#    /    \     /    \     /    \     /    \
#   m(0) m(0) m(0) m(0) m(0) m(0) m(0) m(0)
#
# Level 0: 1 node
# Level 1: 2 nodes
# Level 2: 4 nodes
# Level 3: 8 nodes
# Total: 2⁰ + 2¹ + 2² + 2³ = 2⁴ - 1 = O(2ⁿ)
```

### 11.3 Pitfall #3: Mengabaikan Input yang Berbeda

```python
# ❌ SALAH — Mengklaim O(n²) padahal ada dua input berbeda
def compare_arrays(arr1: list, arr2: list) -> bool:
    for x in arr1:      # O(n) — n = len(arr1)
        for y in arr2:  # O(m) — m = len(arr2)
            if x == y:
                return True
    return False

# ✅ BENAR — Kompleksitas adalah O(n × m), BUKAN O(n²)
# O(n²) hanya valid jika len(arr1) == len(arr2)
# Jika arr1 = 10 elemen, arr2 = 1.000.000 elemen:
#   O(n²) → 10² = 100 (SALAH!)
#   O(n×m) → 10 × 1.000.000 = 10.000.000 (BENAR!)
```

### 11.4 Pitfall #4: Mengabaikan Space Complexity

```python
# ❌ SALAH — Hanya fokus pada time complexity
def get_all_substrings(s: str) -> list:
    """
    Time: O(n²) ← Diperhatikan
    Space: O(n²) ← SERING DILUPAKAN!
    """
    result = []
    n = len(s)
    for i in range(n):
        for j in range(i+1, n+1):
            result.append(s[i:j])  # Menyimpan n²/2 substring!
    return result

# Untuk string 10.000 karakter:
# Jumlah substring: ~50.000.000
# Rata-rata panjang: ~5.000 karakter
# Total memori: ~250 GB ← CRASH!
```

---

## Seksi 12 — Hands-On Exercise

### Exercise 1 — Identifikasi Kompleksitas (Beginner)

```python
"""
INSTRUKSI: Tentukan Time Complexity dan Space Complexity
dari setiap fungsi berikut. Jelaskan alasannya.
"""

# Fungsi A
def func_a(n: int) -> int:
    total = 0
    for i in range(n):
        for j in range(n):
            total += i * j
    return total
# Time: ___  Space: ___  Alasan: ___

# Fungsi B
def func_b(arr: list) -> bool:
    return len(arr) % 2 == 0
# Time: ___  Space: ___  Alasan: ___

# Fungsi C
def func_c(n: int) -> list:
    result = []
    for i in range(n):
        result.append(i * 2)
    return result
# Time: ___  Space: ___  Alasan: ___

# Fungsi D
def func_d(arr: list) -> list:
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = func_d(arr[:mid])
    right = func_d(arr[mid:])
    return left + right  # Asumsikan merge O(n)
# Time: ___  Space: ___  Alasan: ___
```

### Exercise 2 — Optimasi Kode (Intermediate)

```python
"""
INSTRUKSI: Optimasi fungsi berikut dari O(n²) menjadi O(n).
Gunakan data structure yang tepat.
"""

# VERSI LAMBAT — O(n²)
def two_sum_slow(nums: list, target: int) -> tuple | None:
    """
    Cari dua angka dalam nums yang jumlahnya = target.
    Return indeks keduanya.

    Contoh: nums=[2,7,11,15], target=9 → (0,1) karena 2+7=9
    """
    n = len(nums)
    for i in range(n):
        for j in range(i+1, n):
            if nums[i] + nums[j] == target:
                return (i, j)
    return None

# TUGAS: Implementasikan versi O(n) di bawah ini!
def two_sum_fast(nums: list, target: int) -> tuple | None:
    """
    Implementasikan solusi O(n) menggunakan Hash Map.

    Hint: Untuk setiap nums[i], cek apakah (target - nums[i])
    sudah pernah kita lihat sebelumnya.
    """
    # TODO: Implementasikan di sini
    pass
```

### Exercise 2 — Solusi

```python
def two_sum_fast(nums: list, target: int) -> tuple | None:
    """
    Solusi O(n) menggunakan Hash Map.

    Strategi:
    - Simpan {nilai: indeks} di hash map
    - Untuk setiap elemen, cek apakah komplemen (target - elemen)
      sudah ada di hash map
    """
    seen = {}  # {nilai: indeks}

    for i, num in enumerate(nums):  # O(n)
        complement = target - num

        if complement in seen:      # O(1) lookup
            return (seen[complement], i)

        seen[num] = i               # O(1) insert

    return None

# Time Complexity : O(n) — satu pass, setiap operasi O(1)
# Space Complexity: O(n) — hash map menyimpan maksimal n elemen

# Verifikasi:
assert two_sum_fast([2, 7, 11, 15], 9) == (0, 1)
assert two_sum_fast([3, 2, 4], 6) == (1, 2)
assert two_sum_fast([3, 3], 6) == (0, 1)
print("Semua test case passed! ✓")
```

---

## Seksi 13 — Anti-Patterns (Pola yang Harus Dihindari)

### 13.1 Anti-Pattern: Premature Optimization

```python
# ❌ ANTI-PATTERN: Mengoptimasi sebelum ada masalah nyata
def calculate_sum_over_engineered(arr: list) -> int:
    """
    Programmer menghabiskan 3 hari membuat ini 'optimal'
    padahal fungsi ini hanya dipanggil sekali saat startup.
    """
    # Implementasi kompleks dengan bit manipulation,
    # SIMD hints, cache-friendly access patterns...
    # (kode yang sulit dibaca dan di-maintain)
    pass

# ✅ LEBIH BAIK: Tulis yang jelas dulu, optimasi jika perlu
def calculate_sum_simple(arr: list) -> int:
    """Simple, readable, maintainable. O(n) sudah cukup."""
    return sum(arr)

# PRINSIP: "Make it work, make it right, make it fast"
#           — Kent Beck
# Optimasi hanya jika profiling menunjukkan bottleneck nyata.
```

### 13.2 Anti-Pattern: Mengabaikan Worst Case

```python
# ❌ ANTI-PATTERN: Hanya test dengan data "baik"
def quicksort_naive(arr: list) -> list:
    """
    Quick Sort dengan pivot = elemen pertama.
    Average case: O(n log n) ← Yang ditest developer
    Worst case: O(n²) ← Yang terjadi di production!
    """
    if len(arr) <= 1:
        return arr
    pivot = arr[0]  # ← MASALAH: pivot buruk untuk data terurut!
    less = [x for x in arr[1:] if x <= pivot]
    greater = [x for x in arr[1:] if x > pivot]
    return quicksort_naive(less) + [pivot] + quicksort_naive(greater)

# Jika input sudah terurut [1,2,3,...,n]:
# Pivot selalu elemen terkecil → partisi tidak seimbang
# Rekursi sedalam n → O(n²) dan O(n) stack → Stack Overflow!

# ✅ LEBIH BAIK: Gunakan median-of-three atau random pivot
import random
def quicksort_robust(arr: list) -> list:
    if len(arr) <= 1:
        return arr
    pivot = random.choice(arr)  # Random pivot menghindari worst case
    less = [x for x in arr if x < pivot]
    equal = [x for x in arr if x == pivot]
    greater = [x for x in arr if x > pivot]
    return quicksort_robust(less) + equal + quicksort_robust(greater)
```

---

## Seksi 14 — Interview Patterns (Pola Interview)

### 14.1 Framework Menjawab Soal Kompleksitas di Interview

```
FRAMEWORK "TRACE-ANALYZE-VERIFY" (TAV):

  STEP 1 — TRACE (Lacak Eksekusi):
    "Mari saya trace dengan contoh kecil dulu..."
    Gunakan n=4 atau n=5 untuk memahami pola.

  STEP 2 — ANALYZE (Analisis Formal):
    "Saya identifikasi loop dan rekursi..."
    Hitung operasi secara sistematis.

  STEP 3 — VERIFY (Verifikasi):
    "Mari kita cek dengan n yang berbeda..."
    Konfirmasi dengan n=1, n=2, n=besar.

CONTOH DIALOG INTERVIEW:

  Interviewer: "Berapa kompleksitas fungsi ini?"

  Kandidat: "Baik, mari saya trace dulu dengan n=4.
             [trace eksekusi]
             Saya lihat ada dua loop bersarang, masing-masing
             berjalan n kali, jadi total operasi adalah n×n = n².
             Time complexity-nya O(n²).
             Untuk space, saya hanya menggunakan beberapa variabel
             konstan, jadi O(1).
             Apakah ada kasus edge yang perlu saya pertimbangkan?"
```

### 14.2 Soal Interview Klasik dengan Analisis

```python
"""
SOAL KLASIK: "Apakah string s1 adalah anagram dari s2?"
Contoh: "listen" dan "silent" → True
        "hello" dan "world"  → False
"""

# SOLUSI 1: Sorting — O(n log n) time, O(n) space
def is_anagram_sort(s1: str, s2: str) -> bool:
    return sorted(s1) == sorted(s2)
    # sorted() = O(n log n), perbandingan = O(n)
    # Total: O(n log n)

# SOLUSI 2: Counter — O(n) time, O(1) space*
from collections import Counter
def is_anagram_counter(s1: str, s2: str) -> bool:
    return Counter(s1) == Counter(s2)
    # Counter() = O(n), perbandingan = O(k) di mana k = jumlah karakter unik
    # Untuk alfabet tetap (26 huruf): O(n) time, O(1) space*
    # *O(1) karena maksimal 26 karakter unik, bukan O(n)

# SOLUSI 3: Array Count — O(n) time, O(1) space (paling eksplisit)
def is_anagram_array(s1: str, s2: str) -> bool:
    if len(s1) != len(s2):
        return False

    count = [0] * 26  # Hanya 26 huruf alfabet → O(1) space

    for c in s1:
        count[ord(c) - ord('a')] += 1  # O(n)
    for c in s2:
        count[ord(c) - ord('a')] -= 1  # O(n)

    return all(c == 0 for c in count)  # O(26) = O(1)

# Time: O(n), Space: O(1) — OPTIMAL untuk alfabet tetap
```

---

## Seksi 15 — Rangkuman Konsep (Summary)

### 15.1 Mind Map Ringkasan

```
                    ┌─────────────────────┐
                    │   DSA & BIG-O       │
                    │   MODULE 01         │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   ┌─────────────┐    ┌─────────────────┐   ┌─────────────┐
   │    DATA     │    │   COMPLEXITY    │   │  ALGORITHM  │
   │  STRUCTURE  │    │    ANALYSIS     │   │  PROPERTIES │
   └──────┬──────┘    └────────┬────────┘   └──────┬──────┘
          │                    │                    │
     Linear/Non-linear    ┌────┴────┐          Finite
     Hash-based           │         │          Definite
     Advanced           Time      Space        Input/Output
                          │         │          Effective
                     O(1) → O(n!)  O(1) → O(n)
```

### 15.2 Tabel Referensi Cepat

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHEAT SHEET BIG-O                            │
├──────────────┬────────────────────────────────────────────────  │
│  Notasi      │  Nama & Contoh Algoritma                         │
├──────────────┼────────────────────────────────────────────────  │
│  O(1)        │  Constant: Array access, Hash lookup             │
│  O(log n)    │  Logarithmic: Binary Search, BST operations      │
│  O(n)        │  Linear: Linear Search, Array traversal          │
│  O(n log n)  │  Linearithmic: Merge Sort, Heap Sort, Quick Sort │
│  O(n²)       │  Quadratic: Bubble Sort, Insertion Sort, nested  │
│              │             loops                                │
│  O(n³)       │  Cubic: Matrix multiplication (naif)             │
│  O(2ⁿ)       │  Exponential: Fibonacci rekursif, subset         │
│              │              enumeration                         │
│  O(n!)       │  Factorial: Permutasi, Traveling Salesman (brute)│
└──────────────┴────────────────────────────────────────────────  │
```

### 15.3 Key Takeaways

```
✦ TAKEAWAY 1: Big-O mengukur PERTUMBUHAN, bukan waktu absolut.
  "Seberapa cepat algoritma melambat saat input membesar?"

✦ TAKEAWAY 2: Selalu analisis WORST CASE kecuali diminta lain.
  Worst case melindungi sistem dari skenario terburuk.

✦ TAKEAWAY 3: Time-Space Trade-off adalah senjata utama.
  Lebih banyak memori → biasanya lebih cepat, dan sebaliknya.

✦ TAKEAWAY 4: Konstanta diabaikan di Big-O, tapi penting di dunia nyata.
  Selalu benchmark dengan data representatif.

✦ TAKEAWAY 5: Pilih algoritma berdasarkan KONTEKS, bukan hanya Big-O.
  Data kecil? Implementasi sederhana mungkin lebih baik.
```

---

## Seksi 16 — Koneksi ke Modul Berikutnya

### 16.1 Peta Perjalanan Belajar

```
MODULE 01 (SEKARANG)              MODULE 02 → 06
Fondasi Big-O                     Array & String Manipulation
         │                                 │
         │    Kompleksitas yang dipelajari  │
         │    akan langsung diaplikasikan   │
         └────────────────────────────────►│
                                           │
                                  MODULE 07 → 10
                                  Linked List & Stack/Queue
                                           │
                                  MODULE 11 → 14
                                  Tree & Graph
                                           │
                                  MODULE 15 → 18
                                  Dynamic Programming
                                           │
                                  MODULE 19 → 20
                                  Advanced Topics & System Design
```

### 16.2 Konsep yang Akan Dibangun di Atas Modul Ini

```
DARI MODULE 01 INI, ANDA AKAN BUTUHKAN:

  □ Analisis O(1) → Memahami Hash Table (Module 06)
  □ Analisis O(log n) → Binary Search Tree (Module 11)
  □ Analisis O(n log n) → Sorting Algorithms (Module 05)
  □ Analisis O(n²) → Mengenali dan mengoptimasi DP (Module 15)
  □ Analisis O(2ⁿ) → Backtracking & Memoization (Module 16)
  □ Space O(n) rekursi → Tree/Graph DFS (Module 12)
```

---

## Seksi 17 — Referensi & Sumber Belajar Lanjutan

### 17.1 Referensi Primer

```
BUKU:
  [1] Cormen, T.H. et al. "Introduction to Algorithms" (CLRS), 4th Ed.
      MIT Press, 2022.
      → Referensi akademik paling komprehensif. Bab 1-3 untuk Big-O.

  [2] Skiena, S.S. "The Algorithm Design Manual", 3rd Ed.
      Springer, 2020.
      → Lebih praktis dari CLRS, banyak contoh nyata.

  [3] Sedgewick, R. & Wayne, K. "Algorithms", 4th Ed.
      Addison-Wesley, 2011.
      → Implementasi Java, tapi konsep universal.

ONLINE:
  [4] Big-O Cheat Sheet: https://www.bigocheatsheet.com
      → Referensi cepat kompleksitas semua algoritma umum.

  [5] Visualgo: https://visualgo.net
      → Visualisasi interaktif algoritma dan data structure.

  [6] MIT OpenCourseWare 6.006:
      https://ocw.mit.edu/courses/6-006-introduction-to-algorithms
      → Kuliah MIT gratis, sangat rigorous.
```

### 17.2 Latihan Soal Tambahan

```
PLATFORM LATIHAN (urutan rekomendasi):
  1. LeetCode — https://leetcode.com
     Tag: "Array", "Two Pointers" untuk pemula
     Soal wajib: #1 Two Sum, #217 Contains Duplicate

  2. HackerRank — https://hackerrank.com
     Section: "Data Structures" → "Arrays"

  3. Codeforces — https://codeforces.com
     Rating 800-1200 untuk pemula

SOAL SPESIFIK MODULE INI:
  □ LeetCode #1   — Two Sum (O(n) dengan hash map)
  □ LeetCode #217 — Contains Duplicate (O(n) dengan set)
  □ LeetCode #242 — Valid Anagram (O(n) dengan counter)
  □ LeetCode #704 — Binary Search (O(log n))
  □ LeetCode #169 — Majority Element (O(n) Boyer-Moore)
```

---

## Seksi 18 — Glossary (Glosarium Teknis)

```
┌─────────────────────────────────────────────────────────────────┐
│                        GLOSARIUM                                │
├──────────────────────┬──────────────────────────────────────────┤
│  TERM                │  DEFINISI                               │
├──────────────────────┼──────────────────────────────────────────┤
│  Algorithm           │  Sekumpulan instruksi terbatas dan      │
│                      │  terurut untuk memecahkan masalah       │
├──────────────────────┼──────────────────────────────────────────┤
│  Asymptotic Analysis │  Analisis perilaku fungsi saat n → ∞   │
├──────────────────────┼──────────────────────────────────────────┤
│  Average Case        │  Kompleksitas untuk input rata-rata     │
│                      │  (distribusi probabilistik)             │
├──────────────────────┼──────────────────────────────────────────┤
│  Best Case           │  Kompleksitas untuk input paling        │
│                      │  menguntungkan (Omega notation)         │
├──────────────────────┼──────────────────────────────────────────┤
│  Big-O Notation      │  Notasi untuk upper bound kompleksitas  │
│                      │  (worst case behavior)                  │
├──────────────────────┼──────────────────────────────────────────┤
│  Call Stack          │  Struktur memori untuk menyimpan frame  │
│                      │  fungsi yang sedang aktif               │
├──────────────────────┼──────────────────────────────────────────┤
│  Complexity          │  Ukuran sumber daya (waktu/ruang) yang  │
│                      │  dibutuhkan algoritma relatif terhadap n│
├──────────────────────┼──────────────────────────────────────────┤
│  Data Structure      │  Cara terorganisir menyimpan data untuk │
│                      │  operasi yang efisien                   │
├──────────────────────┼──────────────────────────────────────────┤
│  Dominant Term       │  Term yang tumbuh paling cepat dalam    │
│                      │  ekspresi kompleksitas                  │
├──────────────────────┼──────────────────────────────────────────┤
│  Hash Map / Dict     │  Struktur data key-value dengan lookup  │
│                      │  O(1) average case                      │
├──────────────────────┼──────────────────────────────────────────┤
│  In-place Algorithm  │  Algoritma yang tidak membutuhkan       │
│                      │  memori tambahan signifikan (O(1) space)│
├──────────────────────┼──────────────────────────────────────────┤
│  Input Size (n)      │  Ukuran atau jumlah elemen input yang   │
│                      │  menjadi variabel dalam analisis        │
├──────────────────────┼──────────────────────────────────────────┤
│  Memoization         │  Teknik caching hasil komputasi untuk   │
│                      │  menghindari perhitungan berulang       │
├──────────────────────┼──────────────────────────────────────────┤
│  Recursion           │  Fungsi yang memanggil dirinya sendiri  │
│                      │  dengan subproblem yang lebih kecil     │
├──────────────────────┼──────────────────────────────────────────┤
│  Space Complexity    │  Jumlah memori yang digunakan algoritma │
│                      │  relatif terhadap ukuran input          │
├──────────────────────┼──────────────────────────────────────────┤
│  Stable Sort         │  Algoritma sort yang mempertahankan     │
│                      │  urutan relatif elemen yang sama        │
├──────────────────────┼──────────────────────────────────────────┤
│  Time Complexity     │  Jumlah operasi yang dilakukan algoritma│
│                      │  relatif terhadap ukuran input          │
├──────────────────────┼──────────────────────────────────────────┤
│  Trade-off           │  Kompromi antara dua properti yang      │
│                      │  saling bertentangan (time vs space)    │
├──────────────────────┼──────────────────────────────────────────┤
│  Upper Bound         │  Batas atas pertumbuhan fungsi;         │
│                      │  algoritma tidak akan lebih buruk dari  │
│                      │  ini dalam semua kasus                  │
├──────────────────────┼──────────────────────────────────────────┤
│  Worst Case          │  Kompleksitas untuk input yang paling   │
│                      │  tidak menguntungkan (Big-O notation)   │
└──────────────────────┴──────────────────────────────────────────┘
```

---

## Seksi 19 — Self-Assessment Quiz

### Quiz 1 — Pilihan Ganda

```
PERTANYAAN 1:
  Fungsi berikut memiliki Time Complexity:

  def func(n):
      for i in range(n):
          for j in range(10):  # ← Selalu 10 iterasi, bukan n
              print(i, j)

  A) O(n²)
  B) O(10n)
  C) O(n)      ← JAWABAN BENAR
  D) O(10)

  PENJELASAN: Loop dalam selalu 10 iterasi (konstan).
  O(n × 10) = O(10n) = O(n). Konstanta dibuang.

─────────────────────────────────────────────────────────────────

PERTANYAAN 2:
  Manakah yang BENAR tentang Big-O notation?

  A) O(n²) selalu lebih lambat dari O(n) untuk semua nilai n
  B) O(n²) lebih lambat dari O(n) untuk n yang cukup besar ← BENAR
  C) Big-O mengukur waktu eksekusi dalam milidetik
  D) O(1) berarti hanya ada satu operasi

  PENJELASAN: Untuk n kecil, O(n²) bisa lebih cepat jika
  konstantanya kecil. Big-O hanya valid untuk n → ∞.

─────────────────────────────────────────────────────────────────

PERTANYAAN 3:
  Space Complexity dari fungsi rekursif factorial(n) adalah:

  A) O(1)
  B) O(log n)
  C) O(n)      ← JAWABAN BENAR
  D) O(n²)

  PENJELASAN: Setiap panggilan rekursif menambah satu frame
  ke call stack. Untuk factorial(n), ada n frame aktif
  sekaligus → O(n) space.
```

### Quiz 2 — Analisis Kode

```python
"""
PERTANYAAN: Tentukan Time dan Space Complexity.
Jelaskan langkah demi langkah.
"""

def mystery_function(nums: list) -> list:
    n = len(nums)
    result = []

    for i in range(n):              # Loop A
        if nums[i] > 0:
            for j in range(i, n):   # Loop B
                result.append(nums[i] + nums[j])

    return result

"""
JAWABAN:

Time Complexity:
  - Loop A: berjalan n kali
  - Loop B: berjalan (n-i) kali untuk setiap i
  - Total iterasi: Σ(n-i) untuk i=0 sampai n-1
                 = n + (n-1) + (n-2) + ... + 1
                 = n(n+1)/2
                 = O(n²)
  - Catatan: kondisi 'if nums[i] > 0' tidak mengubah worst case
    karena dalam worst case semua elemen positif

Time Complexity: O(n²)

Space Complexity:
  - result list: dalam worst case menyimpan n(n+1)/2 elemen
  - Space Complexity: O(n²)
"""
```

### Quiz 3 — Desain Algoritma

```
PERTANYAAN:
  Diberikan array integer yang TIDAK terurut dengan n elemen.
  Anda perlu menjawab q pertanyaan, masing-masing bertanya:
  "Apakah nilai X ada dalam array?"

  Anda memiliki dua pilihan:
  A) Linear Search untuk setiap pertanyaan: O(n) per query
  B) Build Hash Set sekali, lalu O(1) per query

  Kapan pilihan A lebih baik dari B?
  Kapan pilihan B lebih baik dari A?

JAWABAN:
  Total cost A: O(q × n)
  Total cost B: O(n) build + O(q × 1) = O(n + q)

  Pilihan A lebih baik jika:
    q × n < n + q
    q(n-1) < n
    q < n/(n-1) ≈ 1 (untuk n besar)
    → Hanya jika q = 1 (satu pertanyaan saja)!

  Pilihan B lebih baik jika:
    q ≥ 2 (dua atau lebih pertanyaan)
    Dan memori O(n) tersedia.

  KESIMPULAN: Hampir selalu gunakan Hash Set jika ada
  lebih dari satu query. Trade-off: O(n) space untuk
  O(1) per query.
```

---

## Seksi 20 — Instructor Notes & Facilitation Guide

### 20.1 Panduan Pengajaran

```
DURASI YANG DISARANKAN:
  ┌─────────────────────────────────────────────────────────────┐
  │  Seksi 01-04 (Konsep Dasar)          : 20 menit            │
  │  Seksi 05-06 (Mekanisme & Diagram)   : 25 menit            │
  │  Seksi 07-08 (Contoh & Studi Kasus)  : 30 menit            │
  │  Seksi 09-11 (Trade-offs & Pitfalls) : 20 menit            │
  │  Seksi 12    (Hands-on Exercise)     : 30 menit            │
  │  Seksi 19    (Quiz & Assessment)     : 15 menit            │
  │  Total                               : ~140 menit          │
  └─────────────────────────────────────────────────────────────┘
```

### 20.2 Titik Diskusi Kritis

```
DISKUSI 1 — Pembuka (5 menit):
  "Pernahkah aplikasi yang Anda gunakan tiba-tiba sangat lambat?
   Menurut Anda, apa penyebabnya?"
  → Arahkan ke: data besar + algoritma buruk = disaster

DISKUSI 2 — Setelah Diagram Kurva (5 menit):
  "Jika Anda adalah CTO startup yang baru dapat 10 juta user,
   algoritma mana yang paling Anda takuti di codebase Anda?"
  → Jawaban: O(n²) atau lebih buruk di hot path

DISKUSI 3 — Setelah Studi Kasus (10 menit):
  "Hash Map memberikan O(1) lookup tapi butuh O(n) space.
   Kapan trade-off ini TIDAK worth it?"
  → Embedded systems, memori sangat terbatas, data sangat besar
```

### 20.3 Misconceptions yang Sering Muncul

```
MISCONCEPTION 1:
  "O(n log n) lebih buruk dari O(n) karena ada log n-nya"
  KOREKSI: O(n log n) masih jauh lebih baik dari O(n²).
  Urutkan: O(n) < O(n log n) << O(n²)

MISCONCEPTION 2:
  "Algoritma dengan Big-O lebih kecil selalu lebih cepat"
  KOREKSI: Untuk n kecil, konstanta bisa mendominasi.
  Selalu benchmark dengan data nyata.

MISCONCEPTION 3:
  "Space Complexity hanya menghitung array/list yang dibuat"
  KOREKSI: Call stack rekursi juga dihitung!
  Rekursi sedalam n = O(n) space meski tidak ada array.

MISCONCEPTION 4:
  "O(1) berarti satu operasi"
  KOREKSI: O(1) berarti KONSTAN, bisa 1 atau 1000 operasi,
  asalkan tidak bergantung pada n.
```

### 20.4 Adaptasi untuk Berbagai Level

```
UNTUK PEMULA ABSOLUT:
  → Fokus pada Seksi 03-07 saja
  → Gunakan analogi sehari-hari (mencari buku di perpustakaan)
  → Skip analisis formal, fokus pada intuisi
  → Latihan: hanya Exercise 1

UNTUK INTERMEDIATE:
  → Semua seksi, termasuk Trade-offs dan Pitfalls
  → Tambahkan diskusi tentang amortized complexity
  → Latihan: Exercise 1 + 2 + Quiz semua

UNTUK ADVANCED (persiapan FAANG):
  → Tambahkan: Master Theorem untuk rekursi
  → Tambahkan: Amortized Analysis (aggregate, accounting, potential)
  → Tambahkan: Probabilistic Analysis
  → Latihan: Semua + soal LeetCode Hard
```

### 20.5 Checklist Kesiapan Peserta untuk Modul Berikutnya

```
Peserta siap lanjut ke Module 02 jika mampu:

  □ Menentukan Big-O dari kode dengan loop bersarang
  □ Membedakan O(n) dan O(n²) secara visual dari kode
  □ Menjelaskan mengapa O(log n) lebih baik dari O(n)
  □ Mengidentifikasi operasi "tersembunyi" (list 'in', string concat)
  □ Memilih antara time dan space trade-off untuk kasus sederhana
  □ Menyelesaikan Two Sum dengan O(n) menggunakan hash map

  Jika belum: Review Seksi 05-07 dan ulangi Exercise 1-2.
```

---

## Penutup Modul

```
╔═════════════════════════════════════════════════════════════════╗
║                    RINGKASAN AKHIR                              ║
╠═════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  Anda telah mempelajari:                                        ║
║                                                                 ║
║  ✦ Definisi Data Structure dan Algorithm                        ║
║  ✦ Mengapa Complexity Analysis penting di dunia nyata           ║
║  ✦ Notasi Big-O: O(1), O(log n), O(n), O(n log n), O(n²), O(2ⁿ)║
║  ✦ Best / Average / Worst Case analysis                         ║
║  ✦ Time vs Space trade-off                                      ║
║  ✦ Common pitfalls dalam analisis kompleksitas                  ║
║  ✦ Cara menganalisis kode Python secara sistematis              ║
║                                                                 ║
║  NEXT: Module 02 — Array & Dynamic Array                        ║
║  "Memahami struktur data paling fundamental dan operasinya"     ║
║                                                                 ║
╚═════════════════════════════════════════════════════════════════╝
```

---

*Dokumen ini dibuat sesuai standar GEMINI.md — Senior Technical Curriculum Architect*
*Course: `datastructures-and-algorithms` | Chapter 01 | Module 01 | v1.0.0*