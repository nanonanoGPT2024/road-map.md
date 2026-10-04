# Bab 03 Module 01: Teknik Two-Pointer (Opposing & Fast-Slow) pada Struktur Data Linear Kontigu

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi karakteristik masalah algoritmik pada struktur data linear (*array* dan *string*) yang dapat direduksi kompleksitas waktunya dari $\mathcal{O}(N^2)$ menjadi $\mathcal{O}(N)$ menggunakan teknik *Two-Pointer*.
- Mengimplementasikan pola *Opposing Pointers* (dua penunjuk berlawanan arah) untuk partisi elemen, validasi simetri, dan pencarian pasangan (*target pair*).
- Mengimplementasikan pola *Fast-Slow Pointers* (dua penunjuk searah berkecepatan berbeda) untuk mutasi array di tempat (*in-place array compaction/mutation*) dengan alokasi memori tambahan $\mathcal{O}(1)$.
- Menganalisis invarian loop (*loop invariants*) guna menjamin terminasi algoritma tanpa risiko *off-by-one errors*, *pointer desynchronization*, atau *infinite loop*.

---

### 2. Prerequisite
Pemahaman mendalam mengenai:
- **Alokasi Memori Kontigu**: Layout memori array 1-D, ukuran tipe data primitif, dan pengalamatan pointer (*pointer arithmetic*).
- **Kompleksitas Asimtotik (Big-O)**: Analisis *Time Complexity* dan *Auxiliary Space Complexity*.
- **Primitif Kontrol Alur**: Penulisan loop `while` dan `for` dengan kondisi terminasi berbasis *index bounds*.

---

### 3. Concept
Teknik *Two-Pointer* adalah paradigma pemrosesan data linear di mana dua buah indeks referensial (dapat berupa indeks array integer atau pointer memori absolut) melakukan traversal ruang pencarian secara bersamaan dengan aturan langkah deterministik. 

Secara arsitektural, ruang pencarian pasangan pada sebuah koleksi berukuran $N$ membentuk matriks planar Cartesian $N \times N$. Pendekatan *brute force* memvalidasi semua sel pada matriks ini, menghasilkan kompleksitas $\mathcal{O}(N^2)$. Teknik *Two-Pointer* mengeksploitasi properti intrinsik dari struktur data yang terurut (*monotonicity*) atau kebutuhan restrukturisasi *in-place* untuk memangkas (*pruning*) seluruh baris atau kolom ruang pencarian pada setiap evaluasi. Hasilnya, ruang pencarian traversal dikonversi dari planar dua dimensi menjadi lintasan linear berdimensi satu, membatasi operasi maksimal sebanyak $2N$ iterasi atau $\mathcal{O}(N)$.

Dua varian fundamental yang dibahas pada modul ini:
1. **Opposing Direction Pointers (Left-Right)**: Dimulai dari batas terluar ($index_{left} = 0$, $index_{right} = N - 1$) dan konvergen menuju satu titik temu di tengah.
2. **Fast-Slow Pointers (Read-Write/Forward Direction)**: Keduanya bergerak searah dari indeks awal, di mana *fast pointer* bertindak sebagai *reader/scanner* dan *slow pointer* bertindak sebagai *writer/compactor*.

---

### 4. Why
Dalam rekayasa sistem berkinerja tinggi:
- **Reduksi Kompleksitas Waktu**: Mengurangi latensi komputasi dari kuadratik $\mathcal{O}(N^2)$ menjadi linear $\mathcal{O}(N)$, menghindari degradasi performa (*exhaustion*) saat memproses dataset berskala ratusan ribu hingga jutaan elemen.
- **Efisiensi Alokasi Memori (Zero Allocation)**: Menghindari alokasi buffer baru pada heap ($\mathcal{O}(1)$ auxiliary space). Hal ini meminimalkan fragmentasi memori dan meniadakan beban *Garbage Collection* (GC) atau overhead alokasi `malloc`/`free`.
- **Optimalisasi Cache Locality**: Array kontigu yang dibaca secara sekuensial (baik maju maupun mundur) memanfaatkan *hardware prefetcher* CPU secara maksimal, menjaga tingkat *L1/L2 cache hit rate* tetap tinggi dibanding struktur berbasis *linked node*.

---

### 5. What
Komponen kunci dari arsitektur *Two-Pointer*:
- **Pointers/Indices ($L, R$ atau $Slow, Fast$)**: Variabel primitif pengontrol status traversal.
- **Monotonicity Condition**: Aturan deterministik matematika/logika yang memutuskan pointer mana yang harus diinkrementasi/didekrementasi tanpa perlu mengecek ulang elemen yang telah dilewati.
- **Termination Predicate**: Kondisi henti yang mutlak valid (misal: $L < R$, $L \le R$, atau $Fast < N$).
- **In-Place Mutation Invariant**: Menjamin bahwa seluruh segmen array dari indeks $0$ hingga $Slow$ selalu berisi elemen yang valid sesuai spesifikasi sistem pada setiap siklus loop.

---

### 6. How
Alur perancangan solusi berbasis *Two-Pointer*:

#### Pola 1: Opposing Pointers (Konvergensi Kiri-Kanan)
1. Inisialisasi: $L \leftarrow 0$, $R \leftarrow N - 1$.
2. Jalankan loop selama kondisi $L < R$ terpenuhi.
3. Evaluasi metrik gabungan: $val = f(arr[L], arr[R])$.
4. Cabang keputusan:
   - Jika $val == target$: Simpan/kembalikan hasil.
   - Jika $val < target$: Eliminasi elemen ke-$L$ karena penjumlahan dengan elemen maksimal yang tersisa ($arr[R]$) tetap tidak memenuhi syarat. Lakukan $L \leftarrow L + 1$.
   - Jika $val > target$: Eliminasi elemen ke-$R$ karena penjumlahan dengan elemen minimal yang tersisa ($arr[L]$) melebihi syarat. Lakukan $R \leftarrow R - 1$.

#### Pola 2: Fast-Slow Pointers (Read-Write In-Place)
1. Inisialisasi: $slow \leftarrow 0$, $fast \leftarrow 0$.
2. Iterasi $fast$ dari $0$ hingga $N - 1$.
3. Evaluasi predikat seleksi: $P(arr[fast])$.
4. Jika predikat bernilai *true*:
   - Tulis nilai: $arr[slow] \leftarrow arr[fast]$.
   - Inkrementasi writer: $slow \leftarrow slow + 1$.
5. Jika predikat bernilai *false*, abaikan elemen dan lanjutkan iterasi $fast$.
6. Kembalikan $slow$ sebagai panjang baru array yang terkompresi.

---

### 7. Analogy
Bayangkan proses pemadatan dokumen di sebuah rak arsip fisik:
- **Fast Pointer (Reader)** adalah asisten audit yang berjalan cepat memeriksa setiap map dari nomor $1$ hingga $N$.
- **Slow Pointer (Writer)** adalah asisten pengarsip yang berdiri di awal rak, menunggu arahan.
- Ketika asisten audit (*fast*) menemukan map yang "Aktif/Valid", ia menyerahkannya ke asisten pengarsip (*slow*) untuk diletakkan di slot saat itu, lalu asisten pengarsip bergeser satu slot ke kanan.
- Jika asisten audit menemukan map "Kedaluwarsa/Duplikat", map tersebut dibuang dan asisten audit langsung melangkah ke map berikutnya, sementara asisten pengarsip tetap diam di posisinya.
- Di akhir penyusuran, semua dokumen valid terkumpul rapi di bagian depan rak tanpa menyisakan ruang kosong, dan tidak ada rak tambahan yang perlu dibeli.

---

### 8. Diagram
#### Diagram 1: Opposing Pointers (Two-Sum Sorted Logic)
```
Index:    0    1    2    3    4    5
Array:  [ 2,   7,  11,  15,  19,  28 ]  Target = 26
          ^                        ^
          L                        R
Step 1: arr[L] + arr[R] = 2 + 28 = 30 > Target -> Geser R ke kiri (R--)

Index:    0    1    2    3    4    5
Array:  [ 2,   7,  11,  15,  19,  28 ]
          ^                   ^
          L                   R
Step 2: arr[L] + arr[R] = 2 + 19 = 21 < Target -> Geser L ke kanan (L++)

Index:    0    1    2    3    4    5
Array:  [ 2,   7,  11,  15,  19,  28 ]
               ^              ^
               L              R
Step 3: arr[L] + arr[R] = 7 + 19 = 26 == Target -> MATCH FOUND [1, 4]
```

#### Diagram 2: Fast-Slow Pointer (In-Place Mutation / Remove Target)
```
Hapus angka 0 dari array:
State Awal:
Index:   0    1    2    3    4
Array: [ 0,   1,   0,   3,  12 ]
         ^
      S, F (S=0, F=0: arr[F] == 0, S diam, F++)

Iterasi F=1:
Index:   0    1    2    3    4
Array: [ 1,   1,   0,   3,  12 ]  -> Salin arr[1] ke arr[0], S++, F++
              ^    ^
              S    F

Iterasi F=2:
Index:   0    1    2    3    4
Array: [ 1,   1,   0,   3,  12 ]  -> arr[F] == 0, S diam, F++
              ^         ^
              S         F

Iterasi F=3:
Index:   0    1    2    3    4
Array: [ 1,   3,   0,   3,  12 ]  -> Salin arr[3] ke arr[1], S++, F++
                   ^         ^
                   S         F
```

---

### 9. Simple Example
Implementasi sederhana validasi string palindrom (*Opposing Pointers*) dalam bahasa TypeScript murni:

```typescript
function isPalindrome(s: string): boolean {
    let left = 0;
    let right = s.length - 1;

    while (left < right) {
        if (s[left] !== s[right]) {
            return false; // Pelanggaran simetri terdeteksi
        }
        left++;
        right--;
    }

    return true;
}
```

---

### 10. Practical Example
Implementasi algoritma pemadatan array *in-place* standar industri: Menghapus duplikasi dari *sorted array* di mana setiap elemen unik maksimal muncul dua kali. Pendekatan ini menggunakan algoritma *Fast-Slow Pointer* deterministik dengan proteksi *bounds checking*.

```typescript
/**
 * Memadatkan array terurut sehingga elemen duplikat maksimal muncul 2 kali.
 * Mutasi dilakukan in-place tanpa alokasi memori tambahan.
 * 
 * @param nums - Array integer terurut monotonically non-decreasing.
 * @returns Panjang efektif array yang telah dipadatkan.
 */
function removeDuplicatesAtMostK(nums: number[], k: number = 2): number {
    // Guard clause: jika panjang array <= k, struktur sudah valid secara invarian
    if (nums.length <= k) {
        return nums.length;
    }

    // slow pointer mengindikasikan posisi penulisan selanjutnya
    // Elemen pada index 0 hingga k-1 sudah pasti valid
    let slow = k;

    // fast pointer mengaudit seluruh sisa elemen array
    for (let fast = k; fast < nums.length; fast++) {
        // Bandingkan elemen saat ini (fast) dengan elemen k posisi di belakang slow.
        // Karena array terurut, jika nums[fast] !== nums[slow - k], 
        // maka kemunculan elemen nums[fast] belum melebihi limit k.
        if (nums[fast] !== nums[slow - k]) {
            nums[slow] = nums[fast];
            slow++;
        }
    }

    // slow merepresentasikan panjang logis array yang valid
    return slow;
}

// Bukti Eksekusi:
const buffer = [1, 1, 1, 2, 2, 3];
const newLength = removeDuplicatesAtMostK(buffer, 2);
console.log(`Panjang Baru: ${newLength}`); // Output: 5
console.log(`Array Hasil:`, buffer.slice(0, newLength)); // Output: [1, 1, 2, 2, 3]
```

---

### 11. Real World Example
**Domain: Engine Pemrosesan Finansial / Matching Engine Log Order Book**

Dalam sistem analitik perdagangan frekuensi tinggi (*High-Frequency Trading*), platform menerima aliran jutaan catatan transaksi terurut per detik. Engine perlu membersihkan entri pembatalan pesanan (*canceled orders*) dan memadatkan jejak audit transaksi secara *in-place* pada memori bersama (*shared memory / ring buffer*) sebelum sinkronisasi disk. Mengalokasikan array baru untuk jutaan record per detik akan memicu *Garbage Collection pause* yang mematikan latensi transaksi (*SLA p99.99*).

Implementasi pemadatan memory buffer pesanan menggunakan Fast-Slow pointers:

```typescript
interface OrderRecord {
    orderId: number;
    priceMicroUnits: bigint;
    volume: number;
    isCanceled: boolean;
}

/**
 * Memadatkan Ring Buffer dari entri pembatalan (canceled = true)
 * Menjamin memori L3 cache teroptimasi tanpa instansiasi GC baru.
 */
function compactAuditLogBuffer(records: OrderRecord[]): number {
    const totalRecords = records.length;
    let writeIndex = 0;

    for (let readIndex = 0; readIndex < totalRecords; readIndex++) {
        const currentRecord = records[readIndex];

        // Hanya pertahankan order valid (tidak dibatalkan)
        if (!currentRecord.isCanceled) {
            // Hindari write overhead jika tidak terjadi diskrepansi indeks
            if (writeIndex !== readIndex) {
                records[writeIndex].orderId = currentRecord.orderId;
                records[writeIndex].priceMicroUnits = currentRecord.priceMicroUnits;
                records[writeIndex].volume = currentRecord.volume;
                records[writeIndex].isCanceled = false;
            }
            writeIndex++;
        }
    }

    return writeIndex;
}
```

---

### 12. Trade-offs

| Kategori | Parameter | Analisis & Komparasi |
| :--- | :--- | :--- |
| **Keuntungan** | Kompleksitas Waktu | Reduksi dari $\mathcal{O}(N^2)$ menjadi $\mathcal{O}(N)$ karena ruang pencarian linear. |
| | Kompleksitas Memori | $\mathcal{O}(1)$ Auxiliary Space (tidak memerlukan dynamic heap allocation). |
| | Efisiensi Hardware | Memaksimalkan sequential read pada memory bus (*cache locality*). |
| **Kelemahan** | Prasyarat Urutan | Opposing pointer membutuhkan array yang sudah terurut ($\mathcal{O}(N \log N)$ biaya sort awal jika belum terurut). |
| | Mutasi Data Asli | Fast-Slow pointer merusak data asli pada array sumber jika salinan tidak dibuat sebelumnya. |
| **Kompleksitas** | Time Complexity | $\mathcal{O}(N)$ worst-case dan average-case. |
| | Space Complexity | $\mathcal{O}(1)$ konstan. |
| **Biaya/Overhead**| CPU & Memory Bus | Sangat rendah; instruksi assembly yang dihasilkan berupa *register increment/decrement* murni. |

---

### 13. When To Use
Gunakan teknik Two-Pointer jika:
- Dataset target dialokasikan secara **kontigu** di memori (Array, Vector, String).
- Persoalan menuntut pencarian **pasangan data terurut** yang memenuhi relasi skalar tertentu (misal: $A[i] + A[j] = K$).
- Operasi kompresi, penyaringan (*filtering*), atau pembalikan elemen harus diselesaikan dengan restriksi memori ketat (**in-place**, $\mathcal{O}(1)$ space).
- Menghitung batasan geometris/planar pada array (misal: *Container With Most Water*).

---

### 14. When NOT To Use
Hindari teknik Two-Pointer jika:
- Struktur data yang dihadapi tidak memiliki akses acak $\mathcal{O}(1)$ (*Singly Linked List* untuk opposing pointers, karena pergerakan pointer mundur memerlukan traverse $\mathcal{O}(N)$).
- Data **tidak terurut** dan proses sorting awal ($\mathcal{O}(N \log N)$) melebihi batas waktu yang dialokasikan, sementara algoritma hashing ($\mathcal{O}(N)$ time, $\mathcal{O}(N)$ space) diperbolehkan.
- Dibutuhkan pencarian relasi multivariabel nonsimetris atau pencarian kombinatorik sub-himpunan (*subsets/permutations*) di mana ruang pencarian tidak dapat dieliminasi secara monotonik.

---

### 15. Common Mistakes
1. **Off-by-One Pointer Bounds**: Menggunakan `left <= right` pada persoalan yang mengharuskan pemrosesan dua elemen berbeda, sehingga memicu perbandingan elemen dengan dirinya sendiri.
2. **Infinite Loops**: Lupa menginkrementasi `left` atau mendekrementasi `right` pada blok percabangan kondisional tertentu (`else`/`default`).
3. **Out-of-Bounds Memory Read**: Melakukan dereferensi array sebelum mengecek kondisi batas (`nums[right]` dievaluasi saat `right < 0`).
4. **Mutasi Data saat Iterasi Pointer Bergantung**: Mengubah nilai indeks array yang masih menjadi acuan evaluasi predikat fast-pointer berikutnya tanpa menyimpan salinan sementara (*state corruption*).

---

### 16. Best Practices (Production Checklist)
- [ ] Validasi nilai *null*, *undefined*, atau array kosong sebelum mengakses pointer indeks pertama.
- [ ] Definisikan secara eksplisit kondisi terminasi: Gunakan `left < right` jika memproses pasangan unik, gunakan `left <= right` jika titik pusat tunggal harus diproses.
- [ ] Jika memproses string multiline/karakter khusus, normalisasikan parsing byte/runes terhadap encoding UTF-8 (hindari pemotongan surrogate pairs).
- [ ] Tuliskan *Loop Invariant* di komentar kode untuk mempercepat *peer review* sistem kritis.
- [ ] Manfaatkan optimasi branch prediction: letakkan evaluasi kondisi cabang yang paling sering terjadi (*hot path*) di percabangan teratas `if-else`.

---

### 17. Troubleshooting
- **Gejala: Memory Access Violation / Index Out of Range**:
  - *Akar Masalah*: Evaluasi `right--` tidak terkontrol ketika terdapat iterasi inner-loop bersarang.
  - *Solusi*: Terapkan kondisi guard ganda pada setiap inner loop: `while (left < right && nums[right] === target) right--;`.
- **Gejala: Elemen Hasil Duplikasi Melanggar Batas K**:
  - *Akar Masalah*: Perbandingan fast pointer dilakukan terhadap `slow - 1`, bukan `slow - K`.
  - *Solusi*: Verifikasi formula restriksi window statis: elemen baru aman ditulis jika `nums[fast] !== nums[slow - k]`.

---

### 18. Exercise
Selesaikan secara mandiri tanpa menggunakan struktur data hash map/set:
1. **Two Sum II (Input Array Is Sorted)**: Diberikan array bilangan bulat 1-indexed yang sudah terurut menaik, cari dua angka yang jika dijumlahkan menghasilkan nilai `target`. Return indeks kedua angka tersebut.
2. **Reverse String In-Place**: Diberikan array bertipe karakter, balik urutan karakter tersebut langsung pada array input dengan auxiliary space $\mathcal{O}(1)$.

---

### 19. Challenge
**Deskripsi Masalah (Three-Way Partitioning / Dutch National Flag Problem)**:
Diberikan sebuah array `nums` yang terdiri dari $N$ elemen integer bernilai hanya `0`, `1`, atau `2`. Urutkan array tersebut secara *in-place* sehingga objek dengan nilai sama saling bersebelahan, dengan urutan integer `0`, diikuti `1`, lalu `2`.

**Batasan Teknis**:
- Waktu Komputasi: Tepat satu lintasan traversal (*one-pass* / $\mathcal{O}(N)$).
- Kompleksitas Memori: $\mathcal{O}(1)$ Auxiliary Memory murni.
- Dilarang menggunakan fungsi sorting bawaan bahasa atau penghitungan frekuensi (*counting sort* dua lintasan).

#### Solusi Referensi Industri (Three Pointers Traversal):
```typescript
function sortColors(nums: number[]): void {
    let low = 0;              // Batas akhir dari region nilai 0
    let mid = 0;              // Pointer pembaca elemen aktif
    let high = nums.length - 1; // Batas awal dari region nilai 2

    while (mid <= high) {
        if (nums[mid] === 0) {
            // Tukar nums[low] dan nums[mid], ekspansi region 0
            const temp = nums[low];
            nums[low] = nums[mid];
            nums[mid] = temp;
            low++;
            mid++;
        } else if (nums[mid] === 1) {
            // Region 1 berada di posisi tepat, lewati
            mid++;
        } else {
            // nums[mid] === 2
            // Tukar nums[mid] dan nums[high], ciptakan region 2 di akhir
            const temp = nums[mid];
            nums[mid] = nums[high];
            nums[high] = temp;
            high--;
            // Perhatian: mid TIDAK diinkrementasi di sini karena nilai hasil
            // pertukaran dari index high belum diaudit oleh mid pointer.
        }
    }
}
```

---

### 20. Summary
Teknik *Two-Pointer* merevolusi efisiensi komputasi pada struktur data linear kontigu dengan mengeliminasi redundansi pengecekan state. Melalui pemanfaatan relasi urutan monotonik (*monotonicity*) dan strategi modifikasi memori searah, teknik ini mereduksi ruang komputasi kuadratik menjadi linear ($\mathcal{O}(N)$) dan menjaga konsumsi memori pada batas minimum absolut ($\mathcal{O}(1)$). Penguasaan yang baik terhadap *pointer bounds*, *loop invariants*, dan skema terminasi merupakan prasyarat krusial sebelum melangkah ke teknik yang lebih kompleks seperti *Dynamic Sliding Window* dan *Two-Pointer Graph Traversal*.