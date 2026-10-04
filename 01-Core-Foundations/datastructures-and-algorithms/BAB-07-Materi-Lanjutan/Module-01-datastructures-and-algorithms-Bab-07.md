## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** DSA-CORE-0701
* **Nama Modul:** Paradigma Algoritma: Divide & Conquer dan Greedy
* **Kategori:** 01-Core-Foundations
* **Tingkat Kesulitan:** Intermediate / Lanjutan Dasar
* **Prasyarat:** 
  * Analisis Kompleksitas Asimptotik (Big-O, Big-$\Omega$, Big-$\Theta$)
  * Rekursi & Call Stack Mechanics
  * Struktur Data Dasar (Array, Linked List, Priority Queue/Heap, Binary Tree)
* **Estimasi Waktu Penyelesaian:** 8 – 10 Jam Pembelajaran Mandiri + Hands-on Coding
* **Target Audiens:** Software Engineer, Systems Architect, Mahasiswa Ilmu Komputer, Peserta Persiapan Technical Interview (FAANG/Tier-1 Tech).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedakan Paradigma:** Mengidentifikasi secara deterministik kapan suatu domain persoalan komputasional dapat diselesaikan dengan pendekatan *Divide & Conquer* (D&C), *Greedy*, atau kapan kedua paradigma tersebut tidak valid.
2. **Membongkar Rekurensi D&C Menggunakan Master Theorem:** Mentransformasikan relasi rekurensi bentuk $T(n) = aT(n/b) + f(n)$ ke dalam kompleksitas waktu eksplisit menggunakan *Master Theorem* dan *Recursion Tree Method*.
3. **Membuktikan Kebenaran Algoritma Greedy:** Mengkonstruksi argumen pembuktian formal menggunakan metode *Greedy-Choice Property* dan *Optimal Substructure* melalui teknik *Exchange Argument* (*Argumen Pertukaran*).
4. **Mengimplementasikan Solusi D&C Berkinerja Tinggi:** Menulis implementasi algoritma pemecahan masalah non-trivial berbasis D&C dengan alokasi memori minimal dan penanganan *base cases* yang aman.
5. **Mengimplementasikan Algoritma Greedy Optimal:** Merancang struktur data penyokong yang efisien (seperti Heap/Sorting) guna mempertahankan kompleksitas waktu sub-kuadratik $O(n \log n)$ pada algoritma berbasis serakah.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                         PARADIGMA PEMECAHAN MASALAH
                                     |
         +---------------------------+---------------------------+
         |                                                       |
   DIVIDE & CONQUER                                           GREEDY
         |                                                       |
  +------+------+                                         +------+------+
  | Tiga Fase   |                                         | Dua Pilar   |
  | Inti:       |                                         | Kebenaran:  |
  | 1. Divide   |                                         | 1. Greedy   |
  | 2. Conquer  |                                         |    Choice   |
  | 3. Combine  |                                         | 2. Optimal  |
  +------+------+                                         |    Substruct|
         |                                                +------+------+
  +------+------+                                                |
  | Analisis    |                                         +------+------+
  | Rekurensi:  |                                         | Metode      |
  | - Master Th.|                                         | Bukti:      |
  | - Recursion |                                         | - Exchange  |
  |   Tree      |                                         |   Argument  |
  +------+------+                                         | - Induksi   |
         |                                                +------+------+
  +------+------+                                                |
  | Aplikasi:   |                                         +------+------+
  | - Merge/    |                                         | Aplikasi:   |
  |   QuickSort |                                         | - Interval  |
  | - Binary Sr.|                                         |   Sched.    |
  | - MaxSubarr |                                         | - Huffman   |
  | - Strassen  |                                         | - Fractional|
  +-------------+                                         |   Knapsack  |
                                                          +-------------+
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pendekatan *brute-force* atau pencarian exhaustive menghasilkan kompleksitas eksponensial ($O(2^n)$, $O(n!)$) atau setidaknya polinomial tinggi ($O(n^3)$, $O(n^4)$) untuk kumpulan data berskala besar. Ketika menangani miliaran entitas data dalam sistem terdistribusi, perbedaan antara $O(n^2)$ dan $O(n \log n)$ adalah perbedaan antara proses yang memakan waktu berhari-hari versus hitungan detik.

1. **Efisiensi Paralelisasi (Divide & Conquer):** Sub-masalah yang dihasilkan oleh fase *divide* bersifat independen satu sama lain. Karakteristik ini menjadi fondasi langsung bagi komputasi paralel dan terdistribusi modern seperti arsitektur MapReduce, Multithreading Work-Stealing Pool, dan algoritma graf skala petabyte.
2. **Kecepatan Eksekusi Ekstrem (Greedy):** Di ranah operasional berlatensi rendah (misal: *network packet routing*, alokasi bandwidth, sistem kompresi real-time seperti zstd/Huffman), algoritma *greedy* menawarkan laju keputusan instan $O(1)$ atau $O(\log n)$ per langkah tanpa perlu melakukan *backtracking* atau inspeksi state historis secara mendalam.
3. **Optimasi Sumber Daya Sistem:** Memahami kedua paradigma ini melatih insinyur untuk mengeksploitasi struktur inheren dari permasalahan (*problem topology*) sebelum memilih struktur data, menghindari alokasi memori dinamis yang sia-sia (*cache thrashing*), dan mereduksi kompleksitas siklus CPU secara teoritis maupun praktis.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Paradigma Divide & Conquer (D&C)
*Divide and Conquer* adalah paradigma perancangan algoritma yang bekerja secara rekursif melalui tiga langkah struktural:
* **Divide (Membagi):** Memecah masalah utama berukuran $n$ menjadi beberapa sub-masalah berukuran lebih kecil ($n/b$), yang merepresentasikan instance identik dari masalah asli.
* **Conquer (Menaklukkan):** Menyelesaikan masing-masing sub-masalah secara rekursif. Jika ukuran sub-masalah sudah mencapai ukuran batas terkecil (*base case*), selesaikan secara langsung tanpa rekursi lebih lanjut.
* **Combine (Menggabungkan):** Menggabungkan solusi dari sub-masalah tersebut menjadi satu solusi terpadu untuk masalah utama.

### 2. Paradigma Greedy
*Greedy* adalah paradigma algoritmik yang membangun solusi langkah demi langkah, selalu memilih opsi yang tampak terbaik pada saat langkah tersebut diambil (*locally optimal choice*), dengan harapan bahwa rangkaian pilihan lokal ini akan membawa pada solusi akhir yang optimal secara keseluruhan (*globally optimal solution*).

Algoritma Greedy hanya dapat diterapkan secara valid jika masalah memenuhi dua kriteria fundamental:
* **Greedy-Choice Property:** Solusi optimal global dapat dicapai melalui pilihan optimal lokal tanpa pernah merevisi atau membatalkan pilihan sebelumnya (*no backtracking*).
* **Optimal Substructure:** Solusi optimal untuk masalah utama mengandung solusi optimal untuk sub-masalahnya.

### Matriks Perbandingan Paradigma

| Dimensi Parameter | Divide & Conquer | Greedy | Dynamic Programming (Pembanding) |
| :--- | :--- | :--- | :--- |
| **Pola Keputusan** | Rekursif, mendalam ke bawah | Sekuensial, satu arah ke depan | Evaluasi multi-arah, memori state |
| **Sifat Sub-masalah** | Independen dan disjoin | Linear, tereduksi tiap langkah | Saling tumpang tindih (*overlapping*) |
| **Evaluasi Cabang** | Mengevaluasi semua sub-cabang | Hanya mengevaluasi 1 cabang terbaik | Mengevaluasi semua kemungkinan cabang |
| **Kompensasi Mundur** | Menggabungkan hasil (*combine*) | Tidak pernah mundur (*irrevocable*) | Memilih jalur optimal via memoisasi |
| **Tantangan Utama** | Overhead rekursi & Combine cost | Membuktikan kebenaran matematis | Konsumsi memori matriks / memo |

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### Mekanisme Divide & Conquer & Master Theorem

Sebagian besar rekurensi algoritma D&C dapat dinyatakan dalam persamaan diferensial diskret (relasi rekurensi):

$$T(n) = aT\left(\frac{n}{b}\right) + f(n)$$

Dimana:
* $a \ge 1$: Jumlah sub-masalah yang dihasilkan pada setiap level rekursi.
* $b > 1$: Faktor pembagi ukuran data input pada setiap langkah.
* $f(n)$: Kompleksitas waktu untuk membagi masalah (*divide*) dan menggabungkan hasilnya (*combine*).

Nilai kritis yang menentukan batas asimptotik adalah $n^{\log_b a}$. Nilai ini merepresentasikan jumlah daun (*leaf nodes*) pada pohon rekursi.

#### Tiga Kasus Master Theorem:

1. **Kasus 1 (Dominasi Biaya Daun/Conquer):**
   Jika $f(n) = O(n^{\log_b a - \epsilon})$ untuk suatu konstanta $\epsilon > 0$:
   $$T(n) = \Theta(n^{\log_b a})$$

2. **Kasus 2 (Biaya Seimbang di Setiap Level):**
   Jika $f(n) = \Theta(n^{\log_b a} \log^k n)$ di mana $k \ge 0$:
   $$T(n) = \Theta(n^{\log_b a} \log^{k+1} n)$$
   *(Contoh standar Merge Sort: $a=2, b=2, k=0 \implies T(n) = \Theta(n \log n)$).*

3. **Kasus 3 (Dominasi Biaya Root/Combine):**
   Jika $f(n) = \Omega(n^{\log_b a + \epsilon})$ untuk konstanta $\epsilon > 0$, dan memenuhi kondisi keteraturan (*regularity condition*): $a f(n/b) \le c f(n)$ untuk suatu konstanta $c < 1$ dan $n$ yang cukup besar:
   $$T(n) = \Theta(f(n))$$

---

### Mekanisme Greedy & Teknik Pembuktian Exchange Argument

Ketika merancang algoritma Greedy, intuisi sering kali menyesatkan. Algoritma harus dibuktikan menggunakan **Metode Exchange Argument**:

1. Definisikan $A = \{a_1, a_2, \dots, a_k\}$ sebagai solusi yang dihasilkan oleh strategi Greedy.
2. Asumsikan ada solusi optimal hipotetis $O = \{o_1, o_2, \dots, o_m\}$ yang berbeda dari $A$.
3. Identifikasi elemen pertama di mana kedua solusi berbeda: cari indeks $i$ terkecil di mana $a_i \neq o_i$.
4. **Tukar (Exchange):** Konstruksi solusi baru $O'$ dengan menukar elemen $o_i$ dengan $a_i$ ($O' = O \setminus \{o_i\} \cup \{a_i\}$).
5. Buktikan secara matematis bahwa $O'$ tetap valid dan skor/kualitas solusinya tidak lebih buruk dari $O$ ($\text{Kualitas}(O') \ge \text{Kualitas}(O)$).
6. Melalui prinsip induksi matematika, seluruh elemen $O$ dapat digantikan dengan elemen-elemen dari $A$ tanpa menurunkan kualitas, membuktikan bahwa $A$ juga merupakan solusi optimal global.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Visualisasi 1: Eksekusi Rekursi Divide & Conquer (Merge Sort)

```
Level 0:                 [38, 27, 43, 3, 9, 82, 10]              Divide
                                /          \
Level 1:            [38, 27, 43, 3]      [9, 82, 10]            Divide
                       /        \            /     \
Level 2:          [38, 27]    [43, 3]     [9, 82]  [10]         Divide
                   /    \      /   \       /   \     |
Level 3 (Base):  [38]  [27]  [43]  [3]   [9]  [82] [10]         Conquer
                   \    /      \   /       \   /     |
Level 2 Merge:    [27, 38]    [3, 43]     [9, 82]  [10]         Combine
                       \        /            \     /
Level 1 Merge:      [3, 27, 38, 43]       [9, 10, 82]           Combine
                                \          /
Level 0 Result:          [3, 9, 10, 27, 38, 43, 82]             Combine
```

### Visualisasi 2: Pohon Rekursi Matematis D&C ($T(n) = 2T(n/2) + cn$)

```
Cost Level
c(n)                             cn                        = cn
                               /    \
c(n/2)                    c(n/2)    c(n/2)                 = cn
                          /   \      /   \
c(n/4)                 c(n/4)c(n/4)c(n/4)c(n/4)            = cn
                        ...   ...   ...   ...
Base:                  T(1)   T(1)  ...   T(1)             = c * n
                      \______________________/
                         Jumlah Daun = n^(log_2 2) = n
Jumlah Seluruh Level: log_2(n) + 1
Total Biaya: cn * (log_2(n) + 1) = Theta(n log n)
```

### Visualisasi 3: Mekanisme Greedy Choice (Interval Scheduling)

Kriteria Greedy: Pilih interval dengan *Finish Time* ($f_i$) paling awal yang kompatibel.

```
Waktu (t):  0   1   2   3   4   5   6   7   8   9   10
Job A:      [=======]               (s=0, f=3) -> DIPILIH (f paling awal)
Job B:          [=======]           (s=1, f=4) -> DITOLAK (konflik dgn A)
Job C:              [=======]       (s=2, f=5) -> DITOLAK (konflik dgn A)
Job D:                  [=======]   (s=4, f=7) -> DIPILIH (s >= f_A; f paling awal)
Job E:                      [===]   (s=5, f=6) -> DITOLAK (konflik s < f_D jika diurut)
Job F:                          [=======] (s=6, f=9) -> DITOLAK (konflik dgn D)
Job G:                              [===] (s=7, f=9) -> DIPILIH (s >= f_D)

Jalur Keputusan Greedy: Job A -> Job D -> Job G (Total: 3 Job Optimal)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah komparasi implementasi langsung dari kedua paradigma untuk persoalan dasar.

### 1. Divide & Conquer: Maximum Subarray Problem ($O(n \log n)$)

Mencari segmen subarray contiguous dengan jumlah total nilai terbesar.

```python
from typing import List, Tuple

def find_max_crossing_subarray(
    arr: List[int], low: int, mid: int, high: int
) -> Tuple[int, int, int]:
    """
    Fase Combine: Menghitung subarray silang maksimal yang melewati mid.
    Kompleksitas: O(n)
    """
    left_sum = float('-inf')
    total = 0
    max_left = mid
    for i in range(mid, low - 1, -1):
        total += arr[i]
        if total > left_sum:
            left_sum = total
            max_left = i

    right_sum = float('-inf')
    total = 0
    max_right = mid + 1
    for j in range(mid + 1, high + 1):
        total += arr[j]
        if total > right_sum:
            right_sum = total
            max_right = j

    return (max_left, max_right, int(left_sum + right_sum))


def find_maximum_subarray_dc(
    arr: List[int], low: int, high: int
) -> Tuple[int, int, int]:
    """
    Fase Divide & Conquer untuk Maximum Subarray.
    T(n) = 2T(n/2) + O(n) => O(n log n) berdasarkan Master Theorem Kasus 2.
    """
    # Base case: elemen tunggal
    if low == high:
        return (low, high, arr[low])

    mid = (low + high) // 2

    # Conquer: Pecah menjadi dua sisi
    left_low, left_high, left_sum = find_maximum_subarray_dc(arr, low, mid)
    right_low, right_high, right_sum = find_maximum_subarray_dc(arr, mid + 1, high)
    
    # Combine: Cek kemungkinan segmen menyeberangi mid
    cross_low, cross_high, cross_sum = find_max_crossing_subarray(arr, low, mid, high)

    # Ambil nilai maksimal di antara ketiga skenario
    if left_sum >= right_sum and left_sum >= cross_sum:
        return (left_low, left_high, left_sum)
    elif right_sum >= left_sum and right_sum >= cross_sum:
        return (right_low, right_high, right_sum)
    else:
        return (cross_low, cross_high, cross_sum)


# Eksekusi Demo
data = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
l_idx, r_idx, max_val = find_maximum_subarray_dc(data, 0, len(data) - 1)
print(f"[D&C] Subarray Maksimum berada pada indeks {l_idx}..{r_idx} dengan total: {max_val}")
# Output: [D&C] Subarray Maksimum berada pada indeks 3..6 dengan total: 6
```

---

### 2. Greedy: Activity Selection Problem ($O(n \log n)$)

Memilih jumlah aktivitas maksimum yang tidak saling tumpang tindih (*non-overlapping*).

```python
from typing import List, Tuple

def select_max_activities(activities: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
    """
    Memilih aktivitas maksimum menggunakan Greedy-Choice:
    Sorting berdasarkan end_time terkecil secara ascending.
    """
    if not activities:
        return []

    # Sort berdasarkan finish time: O(n log n)
    sorted_activities = sorted(activities, key=lambda act: act[2])

    selected: List[Tuple[str, int, int]] = []
    
    # Pilihan serakah pertama: aktivitas dengan finish time paling awal
    selected.append(sorted_activities[0])
    last_finish_time = sorted_activities[0][2]

    # Iterasi satu kali (O(n)): ambil jika start_time >= last_finish_time
    for i in range(1, len(sorted_activities)):
        name, start, finish = sorted_activities[i]
        if start >= last_finish_time:
            selected.append(sorted_activities[i])
            last_finish_time = finish

    return selected


# Eksekusi Demo: (Nama, Start, Finish)
activity_list = [
    ("Aksi-1", 1, 4),
    ("Aksi-2", 3, 5),
    ("Aksi-3", 0, 6),
    ("Aksi-4", 5, 7),
    ("Aksi-5", 3, 9),
    ("Aksi-6", 5, 9),
    ("Aksi-7", 6, 10),
    ("Aksi-8", 8, 11),
    ("Aksi-9", 8, 12),
    ("Aksi-10", 2, 14),
    ("Aksi-11", 12, 16)
]

chosen = select_max_activities(activity_list)
print(f"[Greedy] Total Aktivitas Terpilih: {len(chosen)}")
for act in chosen:
    print(f"  -> {act[0]}: [{act[1]}, {act[2]}]")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Skenario Sistem Dunia Nyata: Engine Optimasi Jaringan & Alokasi Bandwidth CDN

Sebuah platform Content Delivery Network (CDN) harus mendistribusikan data streaming chunked ke berbagai edge node dengan bandwidth yang terbatas. Terdapat dua sub-komponen algoritma:
1. **D&C:** Algoritma pemilahan latensi logistik secara paralel/hierarkis (*Threshold-Based Closest Pair Matching* antar server edge).
2. **Greedy:** Alokasi kapasitas paket streaming chunked (*Fractional Knapsack Bandwidth Packing*) guna memaksimalkan throughput transfer konten di edge cluster.

Berikut adalah implementasi sistem alokasi paket streaming menggunakan pola **Greedy Fractional Knapsack** dengan tracking telemetri metrik throughput yang siap pakai (*production-grade*):

```python
from dataclasses import dataclass
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@dataclass(frozen=True)
class StreamChunk:
    chunk_id: str
    size_mb: float       # Bobot (Weight)
    priority_val: float  # Nilai Utilitas / Profit (Value)

    @property
    def density(self) -> float:
        """Menghitung Value per Unit Weight (Rasio Densitas)."""
        if self.size_mb <= 0:
            raise ValueError(f"Ukuran chunk {self.chunk_id} harus positif.")
        return self.priority_val / self.size_mb


@dataclass
class AllocationResult:
    chunk_id: str
    allocated_mb: float
    percentage_included: float
    effective_value: float


class EdgeBandwidthScheduler:
    """
    Scheduler Greedy untuk alokasi transmisi chunk data pada edge router.
    Menggunakan paradigma Greedy-Choice Property berdasarkan Value Density.
    Kompleksitas Waktu: O(n log n) di mana n adalah jumlah chunk (karena sorting).
    Kompleksitas Memori: O(n) untuk menyimpan hasil kalkulasi.
    """

    def __init__(self, channel_capacity_mb: float):
        if channel_capacity_mb <= 0:
            raise ValueError("Kapasitas bandwidth harus lebih besar dari 0.")
        self.capacity: float = channel_capacity_mb

    def schedule_transmission(self, chunks: List[StreamChunk]) -> Dict[str, Any]:
        if not chunks:
            logging.warning("Daftar chunk kosong. Tidak ada transmisi yang dijadwalkan.")
            return {"allocations": [], "total_value": 0.0, "consumed_capacity": 0.0}

        # Langkah Greedy 1: Sorting descending berdasarkan rasio (value/weight)
        # Optimal Substructure: Sisa kapasitas akan diisi secara optimal oleh sub-masalah berikutnya
        sorted_chunks = sorted(chunks, key=lambda c: c.density, reverse=True)

        remaining_capacity: float = self.capacity
        total_delivered_value: float = 0.0
        allocations: List[AllocationResult] = []

        for chunk in sorted_chunks:
            if remaining_capacity <= 0.0:
                break

            if chunk.size_mb <= remaining_capacity:
                # Ambil 100% dari chunk ini (Full Inclusion)
                allocated_size = chunk.size_mb
                pct = 1.0
                val = chunk.priority_val
            else:
                # Ambil fraksi dari chunk yang tersisa (Fractional Inclusion)
                allocated_size = remaining_capacity
                pct = remaining_capacity / chunk.size_mb
                val = chunk.priority_val * pct

            remaining_capacity -= allocated_size
            total_delivered_value += val

            allocations.append(
                AllocationResult(
                    chunk_id=chunk.chunk_id,
                    allocated_mb=round(allocated_size, 3),
                    percentage_included=round(pct * 100, 2),
                    effective_value=round(val, 3)
                )
            )

            logging.debug(
                "Chunk %s dialokasikan %.2f MB (%.1f%%)", 
                chunk.chunk_id, allocated_size, pct * 100
            )

        consumed_capacity = self.capacity - remaining_capacity

        return {
            "total_value": round(total_delivered_value, 3),
            "consumed_capacity_mb": round(consumed_capacity, 3),
            "remaining_capacity_mb": round(remaining_capacity, 3),
            "allocations_count": len(allocations),
            "allocations": allocations
        }


# ==========================================
# Uji Integrasi Sistem
# ==========================================
if __name__ == "__main__":
    edge_router = EdgeBandwidthScheduler(channel_capacity_mb=50.0)

    workload = [
        StreamChunk(chunk_id="video-4k-segment-01", size_mb=20.0, priority_val=100.0), # Densitas = 5.0
        StreamChunk(chunk_id="audio-aac-stream-01", size_mb=5.0,  priority_val=50.0),  # Densitas = 10.0
        StreamChunk(chunk_id="telemetry-telecast",  size_mb=10.0, priority_val=30.0),  # Densitas = 3.0
        StreamChunk(chunk_id="video-1080p-fallback", size_mb=30.0, priority_val=90.0),  # Densitas = 3.0
        StreamChunk(chunk_id="live-chat-messages",  size_mb=2.0,  priority_val=40.0),  # Densitas = 20.0
    ]

    result = edge_router.schedule_transmission(workload)

    logging.info("--- METRIK PENJADWALAN CDN GREEDY BERHASIL ---")
    logging.info("Total Utilitas Tercapai: %s", result["total_value"])
    logging.info("Bandwidth Terpakai: %s MB / 50.0 MB", result["consumed_capacity_mb"])
    logging.info("Detail Alokasi Tiap Chunk:")
    for alloc in result["allocations"]:
        print(
            f"  [+] ID: {alloc.chunk_id:<23} | "
            f"Alokasi: {alloc.allocated_mb:>6} MB ({alloc.percentage_included:>6.2f}%) | "
            f"Nilai: {alloc.effective_value:>6}"
        )
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Saat memilih antara D&C, Greedy, atau pendekatan alternatif (seperti Dynamic Programming), pertimbangkan dimensi rekayasa sistem berikut:

| Karakteristik | Divide & Conquer | Greedy | Dynamic Programming |
| :--- | :--- | :--- | :--- |
| **Jaminan Kebenaran Global** | Pasti (jika fase combine benar) | Belum tentu (harus dibuktikan secara ketat) | Pasti (mengevaluasi seluruh state space) |
| **Overhead Memori** | $O(\log n)$ hingga $O(n)$ (Stack Frame & Temp Array) | $O(1)$ atau $O(n)$ (Hanya buffer in-place / sorting) | $O(n)$ hingga $O(n^2)$ (Tabel memo / matriks) |
| **Kemudahan Paralelisasi** | Sangat Tinggi (Struktur percabangan independen) | Rendah (Pilihan langkah $i+1$ bergantung $i$) | Rendah - Menengah (Dependensi DAG antar state) |
| **Sensitivitas Struktur Input** | Kebal terhadap manipulasi urutan elemen dasar | Sangat sensitif terhadap relasi urutan dan lokalitas | Kebal terhadap urutan jika DAG tertutup |
| **Kompleksitas Waktu Rata-rata** | $O(n \log n)$ | $O(n)$ atau $O(n \log n)$ | $O(n^2)$ atau $O(n \cdot W)$ |

### Risiko Trade-Off:
* **Perangkap Greedy (0/1 vs Fractional Knapsack):** Untuk masalah *Fractional Knapsack*, pendekatan Greedy menghasilkan solusi optimal $O(n \log n)$. Namun, jika batasan diubah menjadi *0/1 Knapsack* (item tidak dapat dipecah), Greedy **gagal total** memberikan solusi optimal global, dan sistem harus dialihkan ke *Dynamic Programming* pseudo-polynomial $O(nW)$ atau *Branch & Bound*.
* **Call Stack Exhaustion pada D&C:** Pendekatan D&C yang tidak seimbang (seperti Quick Sort dengan pivot elemen terkecil/terbesar terus-menerus) dapat mendegradasi pohon rekursi menjadi degeneratif ($T(n) = T(n-1) + O(n)$), memicu kompleksitas waktu $O(n^2)$ dan bahaya `RecursionError` / `StackOverflowError` pada kedalaman $n \ge 10.000$.

---

## SEKSI 11 — BEST PRACTICES

1. **Jamin Basis Rekursi (Base Case Guarding):** Pada D&C, definisikan kondisi batas $n \le 1$ atau $n \le 2$ secara eksplisit sebelum menjalankan pembelahan rekursif untuk mencegah rekursi tak hingga (*infinite loop*).
2. **Minimalkan Alokasi Memori pada Fase Combine:** Hindari inisialisasi array baru di dalam loop combine rekursif. Lebih disukai menggunakan satu array penyangga (*pre-allocated auxiliary buffer*) yang diteruskan melalui parameter referensi (sebagaimana dilakukan pada *In-Place Merge Sort* teroptimasi).
3. **Validasi Karakteristik Masalah Sebelum Menggunakan Greedy:** Selalu lakukan pengujian terhadap *counter-example* sederhana sebelum menerapkan Greedy di lingkungan produksi. Jika satu contoh tereksekusi secara sub-optimal, jangan paksakan Greedy; gunakan Dynamic Programming.
4. **Optimalkan Struktur Sort/Selection:** Pada Greedy, jika hanya membutuhkan k-elemen terbaik pertama, gunakan struktur data *Min/Max Heap* atau algoritma *Quickselect* ($O(n)$ average) daripada melakukan pengurutan penuh $O(n \log n)$ pada seluruh array data.
5. **Gunakan Tail Recursion Elimination:** Jika menggunakan compiler yang mendukung optimasi *Tail-Call Optimization* (seperti C++ / Rust), susun algoritma rekursif sedemikian rupa agar operasi penutup dapat dioptimasi menjadi loop sekuensial secara internal oleh compiler.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Masalah Koin Pecahan Sepele (The Coin Change Fallacy)
* **Pola Buruk:** Berasumsi bahwa algoritma Greedy selalu optimal untuk *Coin Change Problem* dengan sembarang set pecahan.
* **Mengapa Bermasalah:** Misalkan denominasi koin yang tersedia adalah $\{1, 3, 4\}$ dan target nilai kembalian adalah `6`. Pendekatan Greedy akan mengambil $4$, lalu $1$, lalu $1$ (total 3 koin: $4+1+1$). Namun, solusi optimal global adalah $3 + 3$ (hanya 2 koin).
* **Solusi Perbaikan:** Buktikan apakah denominasi membentuk *Canonical Coin System*. Jika tidak canonical, gunakan Dynamic Programming.

### 2. Off-By-One Indexing pada Fase Divide D&C
* **Pola Buruk:** Salah menentukan titik tengah `mid` dan batas bawah/atas sub-rekursi.
  ```python
  # BUG: Potensi Infinite Recursion jika low + 1 == high
  mid = (low + high) // 2
  solve(low, mid)
  solve(mid, high)  # Jika low=0, high=1 -> mid=0. solve(0, 1) dipanggil berulang kali tanpa henti!
  ```
* **Solusi Perbaikan:** Gunakan batas strictly disjoin:
  ```python
  mid = low + (high - low) // 2
  solve(low, mid)
  solve(mid + 1, high)
  ```

### 3. Mengabaikan Integer Overflow saat Menghitung Titik Tengah
* **Pola Buruk:** Menulis `mid = (low + high) // 2` pada bahasa bertipe statis (C, C++, Java).
* **Mengapa Bermasalah:** Jika `low + high` melebihi $2^{31} - 1$, akan terjadi overflow aritmatika integer menjadi bilangan negatif, mengakibatkan *Memory Segmentation Fault*.
* **Solusi Perbaikan:** Gunakan formula matematis aman:
  $$\text{mid} = \text{low} + \frac{\text{high} - \text{low}}{2}$$

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Tingkat: Mudah) — Minimum Number of Platforms (Greedy)
* **Problem:** Diberikan waktu kedatangan (`arr[]`) dan keberangkatan (`dep[]`) semua kereta di sebuah stasiun. Temukan jumlah peron minimum yang dibutuhkan agar tidak ada kereta yang menunggu peron kosong.
* **Input Test Case:**
  * `arr = [900, 940, 950, 1100, 1500, 1800]`
  * `dep = [910, 1200, 1120, 1130, 1900, 2000]`
* **Expected Output:** `3` (Pada rentang waktu 11:00 - 11:20 dibutuhkan 3 peron secara simultan).
* **Petunjuk:** Urutkan waktu kedatangan dan keberangkatan secara terpisah, gunakan dua penunjuk (*two pointers*) secara serakah.

### Latihan 2 (Tingkat: Menengah) — Inversion Count dalam Array (Divide & Conquer)
* **Problem:** Pasangan indeks $(i, j)$ disebut sebagai *inversion* jika $i < j$ dan $arr[i] > arr[j]$. Hitung jumlah total inversion dalam sebuah array numerik dengan kompleksitas waktu $O(n \log n)$.
* **Input Test Case:**
  * `arr = [8, 4, 2, 1]`
* **Expected Output:** `6` (Pasangan: $(8,4), (8,2), (8,1), (4,2), (4,1), (2,1)$).
* **Petunjuk Modifikasi:** Modifikasi algoritma Merge Sort. Pada langkah penggabungan (*merge*), jika elemen di array kanan lebih kecil daripada elemen di array kiri, hitung berapa elemen tersisa di array kiri yang secara definitif lebih besar dari elemen kanan tersebut.

### Latihan 3 (Tingkat: Lanjutan) — Huffman Coding Compression Tree (Greedy)
* **Problem:** Bangun pohon biner Huffman Coding untuk sekumpulan karakter dengan frekuensi kemunculannya masing-masing. Cetak representasi bitstream encoding untuk setiap karakter.
* **Input Test Case:**
  * Karakter dan frekuensi: `{'a': 5, 'b': 9, 'c': 12, 'd': 13, 'e': 16, 'f': 45}`
* **Expected Output:**
  * Panjang prefix unik: karakter dengan frekuensi tertinggi (`f`) harus memiliki representasi bit paling pendek (misal: 1 bit).
* **Struktur Data:** Gunakan *Min-Heap* (Priority Queue). Ambil dua node dengan frekuensi terkecil secara berulang, gabungkan, dan masukkan kembali ke heap.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman teoritis dan praktis Anda:

1. Diberikan relasi rekurensi: $T(n) = 4T(n/2) + n^2$. Menggunakan Master Theorem, tentukan kelas kompleksitas waktu asimptotiknya!
   * A. $\Theta(n^2)$
   * B. $\Theta(n^2 \log n)$
   * C. $\Theta(n^{\log_2 4}) = \Theta(n^2)$
   * D. $\Theta(n^3)$
   * *Jawaban yang Benar:* **B**. 
   * *Penjelasan:* $a = 4, b = 2 \implies n^{\log_b a} = n^{\log_2 4} = n^2$. Di sisi lain, $f(n) = n^2 = \Theta(n^2 \log^0 n)$. Ini memenuhi **Kasus 2** dari Master Theorem dengan $k = 0$, sehingga kompleksitasnya adalah $\Theta(n^2 \log^{0+1} n) = \Theta(n^2 \log n)$.

2. Manakah properti di bawah ini yang **wajib** dipenuhi agar suatu masalah optimasi dapat diselesaikan menggunakan strategi algoritma Greedy secara definitif optimal?
   * A. Overlapping Subproblems dan State Memorization
   * B. Greedy-Choice Property dan Optimal Substructure
   * C. Disjoint Independent Subproblems dan Fast Combine Phase
   * D. Linear Tree Depth dan Tail Recursion
   * *Jawaban yang Benar:* **B**.
   * *Penjelasan:* Greedy membutuhkan kepastian bahwa keputusan lokal dapat menghasilkan keputusan global yang optimal (*greedy choice*) dan solusi optimal sub-masalah membentuk solusi optimal utama (*optimal substructure*). Overlapping subproblems adalah karakteristik Dynamic Programming.

3. Apa kelemahan utama dari algoritma D&C jika diterapkan pada masalah perhitungan Bilangan Fibonacci murni ($F(n) = F(n-1) + F(n-2)$)?
   * A. Fase Divide memakan waktu $O(n^2)$
   * B. Terjadi ledakan sub-masalah tumpang tindih (*overlapping subproblems*) yang berulang, menghasilkan kompleksitas $O(2^n)$
   * C. Master Theorem Kasus 3 tidak dapat dibuktikan
   * D. Array tidak dapat dibagi dua secara seimbang
   * *Jawaban yang Benar:* **B**.
   * *Penjelasan:* Fibonacci memiliki sub-masalah yang saling tumpang tindih secara masif, bukan sub-masalah independen. D&C murni tanpa tabel memoisasi akan menghitung ulang nilai yang sama jutaan kali.

4. Pada teknik pembuktian *Exchange Argument* untuk algoritma Greedy, langkah kritis yang harus dibuktikan adalah:
   * A. Menunjukkan bahwa algoritma greedy selalu menggunakan memori lebih sedikit dibanding brute force.
   * B. Mengganti satu elemen solusi optimal non-greedy dengan elemen greedy tanpa memperburuk nilai fungsi tujuan.
   * C. Menunjukkan bahwa proses divide selalu simetris $n/2$.
   * D. Memastikan tidak ada rekursi yang lebih dalam dari $O(\log n)$.
   * *Jawaban yang Benar:* **B**.
   * *Penjelasan:* Inti dari argumen pertukaran adalah membuktikan bahwa substitusi pilihan serakah ke dalam struktur solusi optimal hipotetis mempertahankan nilai optimumnya.

5. Jika $T(n) = 2T(n/4) + \sqrt{n}$, maka kompleksitasnya adalah:
   * A. $\Theta(\sqrt{n})$
   * B. $\Theta(\sqrt{n} \log n)$
   * C. $\Theta(n)$
   * D. $\Theta(n \log n)$
   * *Jawaban yang Benar:* **B**.
   * *Penjelasan:* $a=2, b=4 \implies n^{\log_4 2} = n^{0.5} = \sqrt{n}$. Nilai $f(n) = \sqrt{n} = \Theta(n^{\log_b a} \log^0 n)$. Ini adalah **Kasus 2** Master Theorem dengan $k=0$, maka hasilnya adalah $\Theta(\sqrt{n} \log n)$.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Referensi:**
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.), Bab 4 (Divide-and-Conquer) & Bab 16 (Greedy Algorithms). The MIT Press.
  * Kleinberg, J., & Tardos, É. (2006). *Algorithm Design*, Bab 4 (Greedy Algorithms) & Bab 5 (Divide and Conquer). Pearson.
  * Dasgupta, S., Papadimitriou, C., & Vazirani, U. (2006). *Algorithms*, Bab 2 & Bab 5. McGraw-Hill.

* **Makalah Akademik Klasik:**
  * Huffman, D. A. (1952). *A Method for the Construction of Minimum-Redundancy Codes*. Proceedings of the IRE, 40(9), 1098-1101.
  * Bentley, J. (1984). *Programming Pearls: Algorithm Design Techniques* (Membahas Maximum Subarray Problem D&C vs Kadane). Communications of the ACM, 27(9), 865-873.

* **Sumber Daring & Platform Latihan:**
  * MIT OpenCourseWare: *6.006 Introduction to Algorithms* (Kuliah Divide and Conquer & Greedy).
  * LeetCode Study Plan: *Problem #53 (Maximum Subarray)*, *Problem #435 (Non-overlapping Intervals)*, *Problem #134 (Gas Station)*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Divide & Conquer** memecah masalah secara rekursif menjadi sub-masalah independen serupa, menaklukkannya pada *base case*, dan menyatukan hasilnya melalui fase *combine*. Kerangka efisiensinya dievaluasi menggunakan **Master Theorem** ($T(n) = aT(n/b) + f(n)$).
* **Greedy** menyusun solusi global melalui keputusan lokal terbaik secara instan tanpa backtracking. Paradigma ini mengutamakan kecepatan eksekusi namun menuntut bukti keabsahan yang ketat melalui **Greedy-Choice Property** dan **Optimal Substructure**.
* Teknik **Exchange Argument** adalah instrumen matematika standar industri untuk memvalidasi algoritma Greedy: membuktikan bahwa mengganti elemen solusi optimal manapun dengan elemen pilihan Greedy tidak pernah mendegradasi skor fungsi tujuan.
* **Perbedaan Inti D&C vs Greedy:** D&C mengevaluasi seluruh sub-jalur secara paralel/rekursif lalu menggabungkannya; Greedy memangkas ruang pencarian dan hanya menempuh satu cabang terbaik secara sekuensial.

---

## SEKSI 17 — GLOSARIUM

1. **Divide and Conquer:** Paradigma algoritmik berbasis dekomposisi rekursif, pemecahan sub-masalah independen, dan rekonstruksi solusi gabungan.
2. **Greedy Strategy:** Pendekatan pemecahan masalah optimasi yang memilih kandidat lokal terbaik pada setiap langkah sekuensial.
3. **Master Theorem:** Rumus instan tertutup untuk menganalisis batas asimptotik dari relasi rekurensi pembagian seimbang.
4. **Optimal Substructure:** Properti suatu masalah optimasi di mana solusi optimal global mengandung solusi optimal untuk setiap sub-masalah bagiannya.
5. **Greedy-Choice Property:** Properti di mana solusi optimal global dapat dijangkau cukup dengan melakukan pilihan serakah lokal tanpa perlu mengevaluasi status masa depan.
6. **Exchange Argument (Argumen Pertukaran):** Teknik pembuktian formal kontradiktif/induktif untuk memverifikasi kebenaran algoritma greedy.
7. **Recurrence Relation:** Persamaan atau pertidaksamaan matematis yang mendeskripsikan fungsi dalam bentuk nilainya pada argumen input yang lebih kecil.
8. **Inversion Count:** Ukuran yang mengindikasikan seberapa jauh sebuah array dari kondisi terurut sempurna; didefinisikan sebagai jumlah pasangan di mana indeks lebih kecil memiliki nilai lebih besar.
9. **Recursion Tree:** Representasi grafis berbentuk pohon dari struktur eksekusi pemanggilan rekursif beserta biaya komputasi di setiap levelnya.
10. **Tail Recursion:** Kondisi khusus pada fungsi rekursif di mana pemanggilan rekursif adalah operasi komputasi paling terakhir yang dieksekusi sebelum nilai dikembalikan.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Titik Miskonsepsi Siswa:** Siswa sering terjebak menganggap Greedy selalu dapat digunakan karena solusinya intuitif dan kodenya pendek. Tekankan bahwa dalam rekayasa perangkat lunak, **Greedy yang salah adalah bug terburuk** karena ia menghasilkan jawaban yang "hampir benar" namun secara matematis sub-optimal.
* **Fokus Pedagogis Master Theorem:** Jangan biarkan siswa sekadar menghafal rumus. Tunjukkan visualisasi *Recursion Tree* (Seksi 07). Jika siswa memahami bahwa Kasus 1 berarti "biaya komputasi terkonsentrasi di daun", Kasus 2 "biaya tersebar merata di setiap level", dan Kasus 3 "biaya didominasi oleh root/combine", mereka tidak akan pernah lupa esensinya.
* **Praktik Laboratorium:** Saat mengajar Latihan 2 (Inversion Count), gunakan ini sebagai jembatan untuk mendemonstrasikan bagaimana memodifikasi algoritma Merge Sort tanpa merusak batas kompleksitas $O(n \log n)$.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023):**
  * Rilis draf kurikulum inisial: Konsep dasar Divide & Conquer dan dasar Greedy.
* **Versi 1.1.0 (Februari 2024):**
  * Penambahan penjabaran formal Master Theorem 3 Kasus lengkap dengan parameter regularitas.
  * Penambahan skema pembuktian matematis *Exchange Argument*.
* **Versi 2.0.0 (Maret 2025) [Current]:**
  * Restrukturisasi total ke dalam format standar 20 Seki GEMINI.md.
  * Penambahan implementasi produksi: *EdgeBandwidthScheduler* (Fractional Knapsack CDN).
  * Penguatan aspek diagram alir ASCII dan standarisasi tipe data Python 3 modern.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `DSA-CORE-0601: Rekursi Lanjutan, Backtracking, dan Tree Traversal`
* **Modul Saat Ini:** `DSA-CORE-0701: Paradigma Algoritma: Divide & Conquer dan Greedy`
* **Modul Berikutnya:** `DSA-CORE-0801: Pemrograman Dinamis (Dynamic Programming): Memoization & Tabulation`
* **Alur Pembelajaran Terkait:**
  * Jalur Pemecahan Masalah: D&C $\to$ Greedy $\to$ Dynamic Programming $\to$ Branch and Bound
  * Jalur Rekayasa Sistem: Struktur Data Dasar $\to$ Optimasi Algoritmik $\to$ Komputasi Terdistribusi (MapReduce)