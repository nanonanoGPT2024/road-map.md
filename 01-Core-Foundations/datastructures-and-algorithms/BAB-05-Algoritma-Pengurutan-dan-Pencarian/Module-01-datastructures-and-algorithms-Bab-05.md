# BAB 05 MODUL 01: FONDASI ALGORITMA PENGURUTAN & PENCARIAN (SORTING & SEARCHING FOUNDATIONS)

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** Computer Science & Software Engineering Core
* **Jalur Pembelajaran:** Data Structures and Algorithms (DSA)
* **Kategori Modul:** `01-Core-Foundations`
* **Kode Modul:** `DSA-C05-M01`
* **Tingkat Kompleksitas:** Intermediate
* **Prasyarat Teknis:** 
  * Analisis Asimptotik Big-O, Big-$\Omega$, Big-$\Theta$ (`DSA-C01-M02`)
  * Struktur Data Dasar: Arrays, Pointer, dan Dynamic Array (`DSA-C02-M01`)
  * Paradigma Rekursi & Divide-and-Conquer (`DSA-C04-M01`)
* **Estimasi Waktu Belajar:** 6 Jam (Teori: 2 Jam, Analisis Algoritmik: 1.5 Jam, Hands-on Lab: 2.5 Jam)
* **Target Stack/Tools:** C++20 atau Python 3.12+ (dilengkapi type hinting), GDB/Valgrind (untuk analisis memori/stack frame), Linux CLI.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Batasan Teoretis (*Information-Theoretic Lower Bound*):** Membuktikan secara matematis mengapa tidak ada algoritma pengurutan berbasis perbandingan (*comparison-based sort*) yang dapat berjalan lebih cepat dari $\Omega(n \log n)$ pada kasus terburuk (*worst-case*).
2. **Menguasai Mekanisme Partisi dan Penggabungan:** Mengimplementasikan skema partisi Lomuto dan Hoare pada Quicksort serta prosedur merge dua arah pada Mergesort tanpa kebocoran memori (*memory leak*).
3. **Mengevaluasi Invarian Perulangan (*Loop Invariants*):** Memformulasikan kondisi pra-syarat, invarian perulangan, dan pasca-syarat matematis pada algoritma Binary Search untuk mengeliminasi *off-by-one errors*.
4. **Memilih Algoritma Sesuai Karakteristik Data:** Menilai secara kritis kapan harus menggunakan algoritma adaptif seperti *Insertion Sort* versus *Quicksort* atau *TimSort* berdasarkan distribusi data, *cache locality*, dan overhead alokasi memori.
5. **Mengimplementasikan Modifikasi Pencarian Kompleks:** Merancang algoritma pencarian biner terspesialisasi untuk mendeteksi batas bawah (*lower bound*), batas atas (*upper bound*), serta elemen pada array yang terotasi (*rotated sorted array*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              [ALGORITMA SORTING & SEARCHING]
                                             │
         ┌───────────────────────────────────┴───────────────────────────────────┐
         ▼                                                                       ▼
   [PENGURUTAN (SORTING)]                                              [PENCARIAN (SEARCHING)]
         │                                                                       │
 ┌───────┴────────────────────────┐                              ┌───────────────┴───────────────┐
 ▼                                ▼                              ▼                               ▼
[Comparison-Based]        [Non-Comparison]             [Unsorted Domain]                 [Sorted Domain]
 │                         │ (Linear Time)               │                                │
 ├─ Quadratic O(n²)        ├─ Counting Sort              └─ Linear Search O(n)            ├─ Binary Search O(log n)
 │  ├─ Bubble Sort         ├─ Radix Sort                                                  ├─ Lower/Upper Bound
 │  ├─ Selection Sort      └─ Bucket Sort                                                 ├─ Exponential Search
 │  └─ Insertion Sort (Adaptive)                                                          └─ Interpolation Search
 │
 └─ Log-Linear O(n log n)
    ├─ Merge Sort (Stable, Out-of-place)
    ├─ Quick Sort (Unstable, In-place, Cache-friendly)
    ├─ Heap Sort (Unstable, In-place)
    └─ Hybrid (Introsort, Timsort)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Algoritma pengurutan dan pencarian bukan sekadar materi klasik wawancara teknis; keduanya merupakan fondasi dari arsitektur perangkat lunak skala tinggi. Dalam komputasi modern:

1. **Efisiensi Mesin Database & Indeks:** Indeks B-Tree dan LSM-Tree pada engine basis data (seperti PostgreSQL, MySQL InnoDB, RocksDB) mengandalkan array terurut dan algoritma pencarian biner untuk navigasi disk page dan block memori secara deterministik dalam waktu $O(\log n)$.
2. **Efisiensi Cache Prosesor (*Hardware Symbiosis*):** Pengurutan data mentransformasikan akses memori acak (*random access*) menjadi akses sekuensial (*spatial locality*). Algoritma pengurutan yang ramah cache (*cache-aware*) seperti Quicksort mengoptimalkan pemanfaatan L1/L2/L3 cache line prosesor, menghasilkan eksekusi riil yang sering kali mengungguli algoritma lain yang kompleksitas operasinya setara.
3. **Optimasi Algoritma Tingkat Tinggi:** Banyak masalah komputasi kompleks dapat direduksi kompleksitasnya dengan melakukan pengurutan terlebih dahulu (*pre-sorting*). Contohnya, pencarian elemen duplikat, kalkulasi interval waktu, operasi himpunan (union, intersection), hingga komputasi graf paling optimal bergantung pada data yang terurut rapi.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Taksonomi Algoritma Pengurutan

Pengurutan adalah proses mereorganisasi sekumpulan elemen dalam suatu koleksi data ke dalam urutan tertentu (biasanya monotonik naik atau turun). Algoritma pengurutan diklasifikasikan berdasarkan atribut kunci:

* **Stabilitas (*Stability*):** Algoritma dikatakan stabil (*stable*) jika mempertahankan urutan relatif elemen-elemen yang memiliki kunci nilai (*key*) yang identik. Jika $A[i] = A[j]$ dan $i < j$ sebelum diurutkan, maka posisi terurut $A[i]$ harus berada sebelum $A[j]$.
* **Penggunaan Memori (*In-Place vs Out-of-Place*):** Algoritma *in-place* hanya membutuhkan memori tambahan konstan $O(1)$ di luar struktur data yang sedang diurutkan (atau $O(\log n)$ pada stack rekursif). Algoritma *out-of-place* memerlukan alokasi tambahan berukuran $O(n)$ untuk menampung elemen sementara.
* **Adaptivitas (*Adaptivity*):** Algoritma adaptif mampu mengeksploitasi data yang sudah terurut sebagian (*partially sorted*) untuk mempercepat waktu eksekusinya menjadi mendekati $O(n)$ daripada fallback ke batas atas terburuknya.

### 2. Teorema Batas Bawah Teoretis (Information-Theoretic Lower Bound)

Untuk mengurutkan himpunan $n$ elemen acak berbasis perbandingan biner ($a < b$ atau $a \ge b$):
* Terdapat $n!$ permutasi yang mungkin dari $n$ elemen tersebut.
* Sebuah pohon perbandingan (*decision tree*) biner harus memiliki setidaknya $n!$ daun (*leaves*) untuk mengidentifikasi permutasi terurut yang benar.
* Ketinggian pohon $h$ merepresentasikan jumlah perbandingan terburuk:
  $$2^h \ge n! \implies h \ge \log_2(n!)$$
* Berdasarkan Aproksimasi Stirling ($\ln(n!) \approx n \ln n - n$):
  $$h \ge \Omega(n \log n)$$
Dengan demikian, tidak ada algoritma pengurutan berbasis perbandingan yang dapat menembus batas bawah $O(n \log n)$ pada kasus terburuk.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Quicksort & Mekanisme Partisi

Quicksort beroperasi menggunakan paradigma *Divide and Conquer*:
1. **Pilih Pivot:** Tentukan elemen penyeimbang data.
2. **Partisi:** Reorganisasi array sedemikian rupa sehingga elemen yang lebih kecil dari pivot berada di sebelah kiri, dan elemen yang lebih besar berada di sebelah kanan. Pivot kini berada di posisi absolutnya.
3. **Rekursi:** Terapkan proses yang sama secara rekursif pada subarray kiri dan kanan.

Terdapat dua skema partisi klasik:
* **Lomuto Partition:** Menggunakan satu penunjuk penelusuran dan satu penunjuk batas partisi. Sederhana dipahami tetapi melakukan pertukaran (*swapping*) lebih banyak dan menurun ke $O(n^2)$ pada array yang berisi nilai seragam.
* **Hoare Partition:** Menggunakan dua penunjuk yang bergerak dari ujung luar saling mendekat ke tengah. Melakukan pertukaran 3 kali lebih sedikit dibandingkan Lomuto dan jauh lebih efisien pada kasus praktis.

### 2. Mergesort

Mergesort menjamin kompleksitas $O(n \log n)$ di segala kondisi:
1. Bagi array secara rekursif menjadi dua bagian di titik tengah: $\lfloor (low + high) / 2 \rfloor$.
2. Basis rekursi tercapai ketika subarray memiliki panjang 1 atau 0.
3. Lakukan proses *merge*: Bandingkan elemen terdepan dari kedua subarray terurut, pindahkan elemen terkecil ke buffer sementara, kemudian salin kembali ke array asal.

### 3. Binary Search

Pencarian biner mengeksploitasi keterurutan data untuk memotong ruang pencarian (*search space*) sebesar separuh pada setiap iterasi:
1. Inisialisasi batas kiri ($low$) dan kanan ($high$).
2. Hitung titik tengah tanpa memicu overflow aritmatika: 
   $$mid = low + \left\lfloor\frac{high - low}{2}\right\rfloor$$
3. Evaluasi $A[mid]$:
   * Jika $A[mid] == target$, terminasi.
   * Jika $A[mid] < target$, eliminasi separuh kiri: $low = mid + 1$.
   * Jika $A[mid] > target$, eliminasi separuh kanan: $high = mid - 1$.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Tracing Partisi Hoare (Quicksort)

Array Awal: `[5, 3, 8, 4, 2, 7, 1, 6]`, Pivot = 5 (Elemen pertama)
Penunjuk $i$ (kiri) mencari elemen $\ge pivot$, Penunjuk $j$ (kanan) mencari elemen $\le pivot$.

```
Kondisi Awal:
 i                               j
[5,  3,  8,  4,  2,  7,  1,  6]
Pivot = 5

Langkah 1:
i maju hingga A[i] >= 5 -> berhenti di A[0] = 5
j mundur hingga A[j] <= 5 -> berhenti di A[6] = 1
 i                           j
[5,  3,  8,  4,  2,  7,  1,  6]  -> i < j, Tukar A[i] dan A[j]!

Setelah Ditukar:
[1,  3,  8,  4,  2,  7,  5,  6]
 i                           j

Langkah 2: Majukan i dan mundurkan j
         i               j
[1,  3,  8,  4,  2,  7,  5,  6]
i berhenti di A[2] = 8 (8 >= 5)
j mundur dan berhenti di A[4] = 2 (2 <= 5)
         i       j
[1,  3,  8,  4,  2,  7,  5,  6]  -> i < j, Tukar A[i] dan A[j]!

Setelah Ditukar:
         i       j
[1,  3,  2,  4,  8,  7,  5,  6]

Langkah 3: Majukan i dan mundurkan j
             j   i
[1,  3,  2,  4,  8,  7,  5,  6]  -> i >= j! Pointer berpapasan (Crossed).
Proses Partisi Berakhir. Kembalikan split index j = 3.
Subarray Kiri:  A[0..3] -> [1, 3, 2, 4] (Semua <= Pivot)
Subarray Kanan: A[4..7] -> [8, 7, 5, 6] (Semua >= Pivot)
```

### 2. Tracing Binary Search Invariant (Closed Interval `[low, high]`)

Target = 7, Data = `[1, 3, 5, 7, 9, 11, 13, 15]`

```
Iterasi 1:
 low                 mid                         high
  │                   │                           │
  ▼                   ▼                           ▼
 [0]  [1]  [2]  [3]  [4]  [5]   [6]   [7]   (Indeks)
 [ 1,   3,   5,   7,   9,  11,  13,  15]   (Nilai)
 mid = 0 + (7 - 0) // 2 = 3 (Nilai = 7)
 Target == A[mid] -> Ditemukan pada indeks 3!
```

Kasus Ekstrem: Mencari Target = 6 (Tidak ada dalam koleksi data)

```
Iterasi 1:
 low=0, high=7, mid=3 -> A[3] = 7
 Target (6) < A[3] (7) -> high = mid - 1 = 2

Iterasi 2:
 low=0, high=2, mid=1 -> A[1] = 3
 Target (6) > A[1] (3) -> low = mid + 1 = 2

Iterasi 3:
 low=2, high=2, mid=2 -> A[2] = 5
 Target (6) > A[2] (5) -> low = mid + 1 = 3

Kondisi Akhir:
 low=3, high=2 -> low > high (Loop Invariant Terputus).
 Return: NOT_FOUND (low menandakan Insertion Point / Lower Bound untuk nilai 6).
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi algoritma pengurutan Quicksort menggunakan partisi Hoare dan Binary Search dengan penanganan *overflow-safe* menggunakan Python 3.12+.

```python
from typing import List, TypeVar

T = TypeVar("T", int, float, str)

def quicksort_hoare(arr: List[T], low: int, high: int) -> None:
    """
    Mengurutkan array in-place menggunakan Quicksort dengan partisi Hoare.
    Kompleksitas Waktu: O(n log n) rata-rata, O(n^2) terburuk.
    Kompleksitas Ruang: O(log n) stack frame.
    """
    if low < high:
        # Menentukan titik pisah partisi
        split_idx = _hoare_partition(arr, low, high)
        # Rekursi subarray kiri dan kanan
        quicksort_hoare(arr, low, split_idx)
        quicksort_hoare(arr, split_idx + 1, high)

def _hoare_partition(arr: List[T], low: int, high: int) -> int:
    pivot = arr[low + (high - low) // 2]
    i = low - 1
    j = high + 1

    while True:
        # Majukan pointer kiri
        i += 1
        while arr[i] < pivot:
            i += 1

        # Mundurkan pointer kanan
        j -= 1
        while arr[j] > pivot:
            j -= 1

        # Jika pointer berpapasan, partisi selesai
        if i >= j:
            return j

        # Tukar elemen di posisi i dan j
        arr[i], arr[j] = arr[j], arr[i]

def binary_search(arr: List[T], target: T) -> int:
    """
    Pencarian biner standar dengan interval tertutup [low, high].
    Mengembalikan indeks jika ditemukan, atau -1 jika tidak ada.
    Kompleksitas Waktu: O(log n).
    Kompleksitas Ruang: O(1).
    """
    low: int = 0
    high: int = len(arr) - 1

    while low <= high:
        # Hindari potensi integer overflow pada bahasa low-level: low + (high - low) // 2
        mid: int = low + (high - low) // 2
        
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1

    return -1

if __name__ == "__main__":
    data = [29, 10, 14, 37, 13, 25, 1, 88]
    print(f"Data Awal   : {data}")
    quicksort_hoare(data, 0, len(data) - 1)
    print(f"Data Terurut: {data}")

    target_val = 25
    idx = binary_search(data, target_val)
    print(f"Pencarian {target_val} berada pada indeks: {idx}")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

**Kasus Nyata:** Pemrosesan Log Metrik Transaksi Finansial Berkecepatan Tinggi.  
Sebuah sistem *trading engine* menerima jutaan log data transaksi per detik. Kita perlu mengurutkan entri log berdasarkan stempel waktu secara stabil (*stable sort*) dan melakukan pencarian audit interval rentang waktu (*range scan*) berkinerja tinggi menggunakan varian *Binary Search* (`lower_bound` dan `upper_bound`).

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class AuditLog:
    timestamp_ms: int
    transaction_id: str
    amount: float

def mergesort_logs(logs: List[AuditLog]) -> List[AuditLog]:
    """
    Implementasi Mergesort stabil untuk tipe data komposit AuditLog.
    Menjamin stabilitas O(n log n) agar urutan relatif transaksi dengan
    timestamp identik tetap terjaga seperti waktu kedatangan aslinya.
    """
    if len(logs) <= 1:
        return logs

    mid = len(logs) // 2
    left_half = mergesort_logs(logs[:mid])
    right_half = mergesort_logs(logs[mid:])

    return _merge(left_half, right_half)

def _merge(left: List[AuditLog], right: List[AuditLog]) -> List[AuditLog]:
    merged: List[AuditLog] = []
    i = j = 0

    while i < len(left) and j < len(right):
        # Penggunaan '<=' memastikan sifat STABLE tetap terjaga
        if left[i].timestamp_ms <= right[j].timestamp_ms:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1

    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged

def lower_bound_timestamp(logs: List[AuditLog], target_ms: int) -> int:
    """
    Mengembalikan indeks pertama di mana log.timestamp_ms >= target_ms.
    Interval pencarian: [low, high) -> Half-open interval.
    """
    low: int = 0
    high: int = len(logs)

    while low < high:
        mid: int = low + (high - low) // 2
        if logs[mid].timestamp_ms < target_ms:
            low = mid + 1
        else:
            high = mid
    return low

def upper_bound_timestamp(logs: List[AuditLog], target_ms: int) -> int:
    """
    Mengembalikan indeks pertama di mana log.timestamp_ms > target_ms.
    """
    low: int = 0
    high: int = len(logs)

    while low < high:
        mid: int = low + (high - low) // 2
        if logs[mid].timestamp_ms <= target_ms:
            low = mid + 1
        else:
            high = mid
    return low

def query_logs_by_range(
    sorted_logs: List[AuditLog], 
    start_ms: int, 
    end_ms: int
) -> List[AuditLog]:
    """
    Mengeksekusi Range Query [start_ms, end_ms] dalam kompleksitas O(log n + k),
    di mana k adalah jumlah elemen dalam rentang tersebut.
    """
    start_idx = lower_bound_timestamp(sorted_logs, start_ms)
    end_idx = upper_bound_timestamp(sorted_logs, end_ms)
    return sorted_logs[start_idx:end_idx]

# --- Simulasi Eksekusi ---
if __name__ == "__main__":
    raw_telemetry: List[AuditLog] = [
        AuditLog(1700000005, "TX_992", 1500.0),
        AuditLog(1700000001, "TX_989", 450.0),
        AuditLog(1700000003, "TX_990", 2500.0),
        AuditLog(1700000001, "TX_991", 70.0),  # Duplikat timestamp
        AuditLog(1700000008, "TX_993", 120.0),
        AuditLog(1700000003, "TX_994", 900.0),  # Duplikat timestamp
    ]

    sorted_telemetry = mergesort_logs(raw_telemetry)
    print("Logs Terurut (Stabil):")
    for log in sorted_telemetry:
        print(f"  [{log.timestamp_ms}] {log.transaction_id}: ${log.amount}")

    # Range Scan: Ambil data dari 1700000002 s/d 1700000005
    query_result = query_logs_by_range(sorted_telemetry, 1700000002, 1700000005)
    print("\nHasil Range Query [1700000002, 1700000005]:")
    for log in query_result:
        print(f"  [{log.timestamp_ms}] {log.transaction_id}")
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Berikut adalah matriks perbandingan performa dan karakteristik intrinsik algoritma:

| Algoritma | Waktu Terbaik (*Best*) | Waktu Rata-rata (*Avg*) | Waktu Terburuk (*Worst*) | Ruang Tambahan (*Space*) | Stabil? | Karakteristik Utama & Penggunaan |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Insertion Sort** | $O(n)$ | $O(n^2)$ | $O(n^2)$ | $O(1)$ | **Ya** | Adaptif; sangat kencang untuk $n \le 32$ atau array nyaris terurut. |
| **Selection Sort** | $O(n^2)$ | $O(n^2)$ | $O(n^2)$ | $O(1)$ | Tidak | Minim jumlah pertukaran memori ($O(n)$ writes), lambat secara umum. |
| **Merge Sort** | $O(n \log n)$ | $O(n \log n)$ | $O(n \log n)$ | $O(n)$ | **Ya** | Kinerja deterministik; standar untuk pengurutan Linked List dan disk-based. |
| **Quick Sort** | $O(n \log n)$ | $O(n \log n)$ | $O(n^2)$ | $O(\log n)$ | Tidak | Sangat ramah cache CPU (*cache locality*); rentan degradasi jika pivot buruk. |
| **Heap Sort** | $O(n \log n)$ | $O(n \log n)$ | $O(n \log n)$ | $O(1)$ | Tidak | *In-place* murni dengan batas $O(n \log n)$, tetapi buruk dalam cache locality. |
| **TimSort** | $O(n)$ | $O(n \log n)$ | $O(n \log n)$ | $O(n)$ | **Ya** | Hibrida (Merge + Insertion). Digunakan secara default pada Python dan Java. |
| **Binary Search** | $O(1)$ | $O(\log n)$ | $O(\log n)$ | $O(1)$ | N/A | Prasyarat mutlak: Array wajib terurut secara kontinu pada memori. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Pivot Median-of-Three:** Pada implementasi Quicksort murni, cegah degradasi $O(n^2)$ akibat data terurut dengan memilih pivot berdasarkan nilai median dari elemen pertama, elemen tengah, dan elemen terakhir:
   $$\text{Pivot} = \text{median}(A[low], A[mid], A[high])$$
2. **Mitigasi Stack Overflow via Tail-Call Optimization:** Pada Quicksort, selalu proses partisi yang lebih kecil terlebih dahulu secara rekursif, dan gunakan perulangan (*loop*) iteratif untuk partisi yang lebih besar guna menjamin kedalaman stack maksimum dibatasi pada $O(\log n)$.
3. **Pencegahan Integer Overflow pada Binary Search:** Jangan pernah menulis `mid = (low + high) / 2`. Pada tipe integer 32-bit bertanda (*signed*), jika $low + high > 2^{31}-1$, ekspresi tersebut akan mengalami integer overflow dan memicu *undefined behavior* atau indeks negatif. Selalu gunakan:
   ```c
   int mid = low + (high - low) / 2;
   ```
4. **Strategi Hybrid Switching:** Jangan jalankan rekursi divide-and-conquer hingga ukuran subarray $n=1$. Ketika ukuran subarray turun di bawah ambang batas (*threshold*) tertentu (umumnya antara 16 hingga 32 elemen), beralihlah ke *Insertion Sort* yang memiliki overhead instruksi jauh lebih rendah.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Off-by-One pada Batas Interval Binary Search:** Mencampurkan paradigma *closed interval* `[low, high]` dengan *half-open interval* `[low, high)`.
   * *Kesalahan:* Menggunakan kondisi `while (low < high)` tetapi memperbarui batas dengan `high = mid - 1`. Hal ini dapat menyebabkan elemen target di indeks batas luput diperiksa.
   * *Aturan:* Jika `while (low <= high)`, gunakan `high = mid - 1`. Jika `while (low < high)`, gunakan `high = mid`.
2. **Asumsi Quicksort Selalu Cepat:** Mengabaikan kasus degradasi Quicksort. Jika dihadapkan pada array berukuran besar dengan banyak nilai kembar (*duplicate keys*), skema partisi 2-way Lomuto membagi data menjadi dua partisi yang sangat tidak seimbang ($O(n^2)$). Solusinya adalah menggunakan skema partisi 3-way (*Dijkstra Dutch National Flag*).
3. **Mengabaikan Overhead Alokasi Mergesort:** Mengalokasikan array pembantu (*temporary buffer*) baru di dalam setiap level rekursi fungsi `merge()`. Hal ini menyebabkan fragmentasi memori dan overhead *garbage collection* atau *malloc*. 
   * *Solusi:* Alokasikan satu buffer tunggal berukuran $O(n)$ di awal eksekusi, lalu teruskan buffer tersebut ke seluruh rantai rekursi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Beginner): Dutch National Flag Partitioning (3-Way Sort)
* **Tantangan:** Diberikan array yang hanya berisi nilai 0, 1, dan 2. Urutkan array tersebut secara *in-place* dalam satu kali penelusuran (*single pass*) $O(n)$ dan memori konstan $O(1)$.
* **Input:** `[2, 0, 2, 1, 1, 0]`
* **Expected Output:** `[0, 0, 1, 1, 2, 2]`
* **Batasan:** Tidak boleh menggunakan fungsi `sort()` bawaan atau alokasi buffer baru.

### Latihan 2 (Intermediate): Search in Rotated Sorted Array
* **Tantangan:** Diberikan sebuah array terurut yang telah dirotasi pada pivot yang tidak diketahui (misal, `[4, 5, 6, 7, 0, 1, 2]`). Tuliskan algoritma pencarian biner modifikasi untuk menemukan indeks dari `target` dalam kompleksitas $O(\log n)$.
* **Input:** `nums = [4, 5, 6, 7, 0, 1, 2]`, `target = 0`
* **Expected Output:** `4`

### Latihan 3 (Advanced): K-th Largest Element without Full Sorting
* **Tantangan:** Temukan elemen terbesar ke-$k$ dalam array tak terurut menggunakan algoritma *Quickselect* (variasi Quicksort). Solusi harus memiliki rata-rata kompleksitas waktu linear $O(n)$.
* **Input:** `nums = [3, 2, 1, 5, 6, 4]`, `k = 2`
* **Expected Output:** `5`

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji pemahaman konseptual Anda:

1. **Mengapa skema perbandingan murni (*comparison-based*) tidak dapat melampaui kompleksitas waktu $\Omega(n \log n)$ pada kasus terburuk?**
   * A. Karena instruksi branch prediction CPU dibatasi oleh cache L1.
   * B. Karena pohon keputusan biner membutuhkan setidaknya $n!$ daun untuk merepresentasikan semua kemungkinan permutasi.
   * C. Karena alokasi memori heap dibatasi oleh kompleksitas logaritmik.
   * D. Karena setiap proses swapping membutuhkan setidaknya $3$ operasi assignment memori.

2. **Diberikan array `[10, 10, 10, 10]`. Algoritma pengurutan manakah yang urutan relatif elemen kuncinya TIDAK dijamin tetap sama?**
   * A. Merge Sort
   * B. Insertion Sort
   * C. Quicksort standar (Lomuto/Hoare)
   * D. Bubble Sort

3. **Operasi modifikasi `mid = low + (high - low) / 2` dirancang untuk menghindari:**
   * A. Floating-point precision error.
   * B. Pembagian dengan angka nol (*divide-by-zero*).
   * C. Integer overflow pada integer fixed-width signed saat penjumlahan $low + high$.
   * D. Rekursi tak terbatas (*infinite loop*).

4. **Kondisi manakah di mana algoritma Insertion Sort lebih unggul secara drastis dibanding Quicksort?**
   * A. Array berukuran sangat masif ($n > 10^7$) dengan distribusi data acak sempurna.
   * B. Array yang elemen-elemennya terbalik total secara menurun.
   * C. Array yang hampir terurut (*nearly-sorted*), di mana setiap elemen hanya berjarak $k \le O(1)$ dari posisi aslinya.
   * D. Array yang diurutkan pada media penyimpanan sekunder berbasis jaringan (*network-attached storage*).

5. **Apa nilai kembalian dari fungsi `lower_bound` pada array `[1, 3, 5, 7, 9]` jika mencari nilai `6`?**
   * A. Indeks 2 (nilai 5)
   * B. Indeks 3 (nilai 7)
   * C. -1 (tidak ditemukan)
   * D. Indeks 4 (nilai 9)

### Kunci Jawaban & Rasional Singkat:
* **1: B** — Berdasarkan model decision tree, kedalaman pohon $h \ge \log_2(n!) = \Omega(n \log n)$.
* **2: C** — Quicksort secara inheren tidak stabil karena proses pertukaran melompati elemen-elemen di tengah array.
* **3: C** — Nilai $low + high$ dapat melampaui nilai maksimum tipe integer bertanda (misal: $2^{31}-1$).
* **4: C** — Insertion sort berjalan dalam waktu linear $O(n)$ untuk array yang hampir terurut.
* **5: B** — `lower_bound` mencari elemen pertama yang bernilai $\ge target$. Elemen pertama $\ge 6$ adalah 7 yang berada pada indeks 3.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Referensi:**
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms (4th Edition)*. Bab 6, 7, 8, dan 9. MIT Press.
  * Knuth, D. E. (1998). *The Art of Computer Programming, Volume 3: Sorting and Searching (2nd Edition)*. Addison-Wesley.
  * Sedgewick, R., & Wayne, K. (2011). *Algorithms (4th Edition)*. Bab 2 (Sorting). Addison-Wesley Professional.
* **Paper & Publikasi Ilmiah:**
  * Hoare, C. A. R. (1962). *Quicksort*. The Computer Journal, 5(1), 10–16.
  * Peters, Tim. (2002). *Timsort Description (listsort.txt)*. Dokumen implementasi standar CPython.
* **Dokumentasi & Standar Kode:**
  * Implementasi `std::sort` (Introsort) pada GNU GCC Libstdc++: [gcc.gnu.org/onlinedocs](https://gcc.gnu.org/)
  * Kode Sumber `sort.go` pada standard library Golang: [go.dev/src/sort](https://go.dev/src/sort/)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
================================================================================
                    CORE CHEAT SHEET: SORTING & SEARCHING
================================================================================
1. LOWER BOUND THEOREM : Perbandingan murni min. Omega(n log n).
2. QUICKSORT           : Rata-rata O(n log n). In-place. Cache friendly. Tidak stabil.
                         Degradasi O(n^2) jika partisi buruk -> mitigasi: Median-of-3.
3. MERGESORT           : O(n log n) pasti. Stabil. Out-of-place (O(n) RAM).
                         Optimal untuk data linked list atau pemrosesan sekuensial.
4. INSERTION SORT      : O(n) terbaik, O(n^2) terburuk. Paling efisien untuk n kecil.
5. BINARY SEARCH       : O(log n) pada domain data terurut kontigu.
                         Gunakan: mid = low + (high - low) / 2.
6. INVARIANT CHECK     : Tentukan interval tertutup [L, R] atau setengah buka [L, R).
================================================================================
```

---

## SEKSI 17 — GLOSARIUM

* **In-Place:** Karakteristik algoritma yang memanipulasi struktur data menggunakan memori pembantu konstan tanpa membuat salinan penuh dari koleksi data tersebut.
* **Stable Sort:** Karakteristik algoritma yang menjamin elemen dengan kunci yang ekuivalen tidak bertukar urutan posisi relatif setelah proses pengurutan selesai.
* **Divide-and-Conquer:** Paradigma perancangan algoritma yang memecah masalah besar menjadi sub-masalah identik yang lebih kecil, menyelesaikannya secara independen, lalu menggabungkan hasilnya.
* **Lower Bound:** Batas bawah matematis terendah dari sumber daya (waktu/ruang) yang diperlukan untuk menyelesaikan suatu masalah komputasi.
* **Loop Invariant:** Proposisi logika matematis yang bernilai benar sebelum perulangan dimulai (*initialization*), tetap bernilai benar selama setiap iterasi (*maintenance*), dan menjamin kebenaran solusi saat perulangan berakhir (*termination*).
* **Pivot:** Elemen acuan yang dipilih dalam algoritma partisi untuk memisahkan data menjadi subset nilai yang lebih kecil dan lebih besar.
* **Cache Locality:** Kecenderungan sistem komputer untuk mengakses lokasi memori yang saling berdekatan dalam jangka waktu yang berdekatan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Metodologi Pengajaran:**
  * Jangan langsung memulai dengan baris kode program. Awali dengan visualisasi fisik: mintalah 8 peserta didik maju ke depan kelas dengan kartu angka acak, lalu simulasikan penunjuk pointer Quicksort (Hoare) menggunakan penanda fisik.
  * Berikan penekanan kuat pada demonstrasi kegagalan *Binary Search*. Buka compiler C++ / Java, tunjukkan secara langsung bagaimana `(low + high) / 2` memicu bug integer overflow ketika array dialokasikan melampaui ukuran maksimum signed 32-bit integer.
* **Titik Hambat Mahasiswa (*Stumbling Blocks*):**
  * Peserta didik sering kebingungan membedakan kapan menggunakan `while (low <= high)` versus `while (low < high)`. Ingatkan bahwa jika interval pencarian mereka adalah interval tertutup `[low, high]`, maka terminasi terjadi saat `low > high` (sehingga kondisinya wajib `low <= high`).
* **Saran Tugas Rumah/Lab:**
  * Uji algoritma pengurutan peserta didik dengan kasus ekstrem (*adversarial test cases*): array dengan seluruh nilai identik, array terurut terbalik, array berpola zig-zag, dan array berukuran $10^6$ elemen.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023):**
  * Rilis perdana modul fondasi algoritma pengurutan dan pencarian.
  * Penyusunan modul sesuai 20 seksi format silabus instruksional GEMINI.md.
  * Integrasi pembuktian Information-Theoretic Lower Bound dan mitigasi overflow midpoint binary search.
* **Versi 1.1.0 (Februari 2024):**
  * Penggantian diagram skema partisi Lomuto menjadi Hoare untuk optimasi performa instruksional.
  * Penambahan skenario praktis finansial (*Audit Log*) dan implementasi varian `lower_bound`/`upper_bound`.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `DSA-C04-M01`: *Paradigma Rekursi, Backtracking, dan Divide-and-Conquer*
* **Modul Saat Ini:** `DSA-C05-M01`: *Fondasi Algoritma Pengurutan dan Pencarian (Sorting & Searching Foundations)*
* **Modul Berikutnya:** `DSA-C05-M02`: *Pencarian Tingkat Lanjut & Algoritma Pengurutan Non-Komparatif (Radix, Counting, dan Bucket Sort)*