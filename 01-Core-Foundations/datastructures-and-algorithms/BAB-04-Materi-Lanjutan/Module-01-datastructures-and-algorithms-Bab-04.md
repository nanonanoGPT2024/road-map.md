## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `CS-DSA-04-01`
* **Nama Modul:** Hash Functions, Hash Tables, dan Mekanisme Resolusi Kolisi
* **Kategori:** `01-Core-Foundations`
* **Bab:** `04 — Hashing & Struktur Data Probabilistik`
* **Tingkat Kesulitan:** Menengah (*Intermediate*)
* **Prasyarat:** `CS-DSA-01-01` (Array & Pointer Memory Layout), `CS-DSA-01-02` (Singly & Doubly Linked List), `CS-DSA-00-01` (Asymptotic Complexity & Amortized Analysis)
* **Estimasi Waktu Belajar:** 180 Menit (Teori: 75 menit, Praktik & Implementasi: 105 menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Memilih Fungsi Hash (Analyze & Select):** Membedakan karakteristik fungsi hash kriptografis vs non-kriptografis (*Avalanche Effect*, distribusi seragam, determinisme) serta memilih fungsi yang tepat (misal: MurmurHash3, xxHash, SipHash) sesuai kebutuhan performa dan mitigasi serangan *Hash DoS*.
2. **Mengimplementasikan Resolusi Kolisi Tingkat Rendah (Implement):** Membangun struktur data Hash Table dari awal (*from scratch*) menggunakan dua paradigma utama: *Closed Addressing* (*Separate Chaining*) dan *Open Addressing* (*Linear Probing*, *Quadratic Probing*, *Double Hashing*) dengan penanganan status *Tombstone*.
3. **Mengoptimalkan Mekanisme Dynamic Resizing (Optimize):** Menghitung rasio *Load Factor* ($\alpha$) secara dinamis dan mengeksekusi operasi *Rehashing* berbasis amortisasi $O(1)$ untuk mencegah degradasi performa ke $O(n)$.
4. **Mengevaluasi Karakteristik Cache Memory (Evaluate):** Mengukur dan membandingkan dampak lokalitas memori (*spatial locality*) dan *CPU cache misses* antara teknik *Separate Chaining* dengan *Open Addressing*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                         [ HASHING ECOSYSTEM ]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
[ Hash Functions ]                                [ Hash Table Storage ]
 ├── Deterministic                                 ├── Bucket Array (Direct Access)
 ├── Uniform Distribution                          ├── Load Factor (α = n / m)
 ├── Avalanche Effect                              └── Dynamic Resizing (Rehashing)
 └── Collision Potential (Pigeonhole Principle)            │
                                                           │
                      ┌────────────────────────────────────┴───────────┐
                      ▼                                                ▼
         [ Closed Addressing ]                                [ Open Addressing ]
        (Separate Chaining)                                 (All keys in array)
         ├── Singly Linked List                                ├── Linear Probing
         └── Balanced BST (fallback)                           ├── Quadratic Probing
                                                               ├── Double Hashing
                                                               └── Tombstone Management
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Operasi pencarian, penyisipan, dan penghapusan pada struktur data linear dasar (Array, Linked List) memerlukan kompleksitas waktu $O(n)$. Walaupun struktur data pohon terurut (seperti AVL Tree atau Red-Black Tree) dapat mereduksi waktu operasi menjadi $O(\log n)$, batas logarithmic ini masih menimbulkan *bottleneck* latensi yang masif pada sistem dengan throughput jutaan operasi per detik, seperti sistem *in-memory cache* (Redis, Memcached), indeks basis data (B-Tree/Hash Indexes), dan *symbol tables* pada kompilator.

Hashing adalah satu-satunya mekanisme yang memungkinkan komputasi *direct-access lookup* dengan ekspektasi kompleksitas waktu konstan $O(1)$. 

Tanpa pemahaman mekanistik yang mendalam tentang distribusi hash, manipulasi bit, resolusi kolisi, dan *cache locality*, insinyur perangkat lunak sering kali menghasilkan sistem yang rentan terhadap degradasi performa eksponensial. Salah satu contoh kerentanan kritis adalah *Hash Collision Denial-of-Service* (Hash DoS), di mana penyerang sengaja mengirimkan payload kunci yang menghasilkan nilai hash identik, memaksa Hash Table berkinerja $O(n)$ dan menghabiskan 100% siklus CPU server.

---

## SEKSI 05 — APA ITU (WHAT)

Secara matematis, **Hash Table** adalah struktur data asosiatif yang mengimplementasikan pemetaan tipe data abstrak (*Abstract Data Type*) kamus (Dictionary) dari himpunan kunci $K$ (*keys*) ke himpunan nilai $V$ (*values*).

1. **Hash Function ($h$):** Suatu fungsi deterministik yang memetakan domain semesta kunci berukuran tak hingga atau sangat besar $U$ ke rentang indeks integer terbatas berukuran $m$:
   $$h: U \to \{0, 1, 2, \dots, m - 1\}$$
2. **Kolisi Hash (*Hash Collision*):** Berdasarkan *Pigeonhole Principle* (Prinsip Sarang Merpati), jika $|U| > m$, maka pasti ada setidaknya dua kunci unik $k_1, k_2 \in U$ di mana $k_1 \neq k_2$ sedemikian sehingga:
   $$h(k_1) = h(k_2)$$
3. **Load Factor ($\alpha$):** Metrik saturasi memori pada tabel:
   $$\alpha = \frac{n}{m}$$
   di mana $n$ adalah jumlah elemen yang tersimpan, dan $m$ adalah kapasitas total *bucket* array.
4. **Collision Resolution Strategy:** Algoritma yang mendikte bagaimana data disimpan dan ditemukan ketika dua atau lebih kunci dialokasikan ke indeks *bucket* yang sama.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Anatomi Fungsi Hash yang Ideal
Fungsi hash yang efektif harus memenuhi empat kriteria fundamental:
* **Deterministik:** Kunci yang identik harus selalu menghasilkan nilai hash yang persis sama selama masa hidup aplikasi.
* **Distribusi Seragam (*Uniformity*):** Kunci harus disebarkan secara merata di seluruh rentang indeks guna meminimalkan probabilitas penggumpalan (*clustering*).
* **Avalanche Effect:** Perubahan satu bit pada input kunci harus mengubah rata-rata 50% bit dari nilai hash output.
* **Efisien Secara Komputasi:** Menggunakan operasi CPU yang murah (seperti *bit-shift*, *bitwise XOR*, dan *multiplication*).

### 2. Resolusi Kolisi: Closed Addressing vs Open Addressing

#### A. Closed Addressing (Separate Chaining)
Setiap indeks *bucket* array menyimpan pointer ke struktur data sekunder, biasanya sebuah *Singly Linked List*.
* **Insert:** Hitung indeks $i = h(k) \pmod m$. Sisipkan pasangan $(k, v)$ ke dalam linked list pada *bucket* $i$.
* **Search:** Evaluasi linked list pada *bucket* $i$ secara linear hingga kunci ditemukan atau pointer mencapai `null`.
* **Karakteristik:** Fleksibel saat $\alpha > 1.0$, namun boros memori karena overhead pointer (`next`) serta rentan terhadap *cache misses* akibat fragmentasi memori *heap*.

#### B. Open Addressing
Semua elemen disimpan langsung di dalam array tabel berukuran tetap. Jika slot $i = h(k) \pmod m$ telah terisi oleh kunci lain, sistem menggunakan *probing sequence* $P(k, i)$ untuk mencari slot kosong berikutnya.

1. **Linear Probing:**
   $$h(k, i) = (h'(k) + i) \pmod m, \quad i \in \{0, 1, \dots, m-1\}$$
   *Masalah:* Mengakibatkan **Primary Clustering**—rentetan slot terisi yang panjang terus membesar, memperlambat waktu pencarian.

2. **Quadratic Probing:**
   $$h(k, i) = (h'(k) + c_1 i + c_2 i^2) \pmod m$$
   *Masalah:* Mereduksi Primary Clustering, namun dapat memicu **Secondary Clustering** (kunci dengan hash awal sama akan mengikuti jalur probing yang persis sama).

3. **Double Hashing:**
   $$h(k, i) = (h_1(k) + i \cdot h_2(k)) \pmod m$$
   Merupakan pendekatan open addressing terbaik karena interval probing bergantung pada fungsi hash sekunder $h_2(k)$. Syarat mutlak: $h_2(k)$ harus koprima (*coprime*) dengan $m$ (sering dipenuhi dengan memilih $m$ bilangan prima dan $h_2(k) = R - (k \pmod R)$ di mana $R < m$).

### 3. Masalah Penghapusan pada Open Addressing: *Tombstones*
Pada *Open Addressing*, jika kita menghapus kunci dan langsung mengosongkan slot (`null`), rantai pencarian (*probing chain*) elemen lain yang bergeser melewati slot tersebut akan terputus sebelum mencapai tujuan. 

**Solusi:** Terapkan penanda khusus berlabel **Tombstone** (atau nilai *Deleted*).
* Operasi **Search** memperlakukan Tombstone sebagai slot terisi (terus melanjutkan probing).
* Operasi **Insert** memperlakukan Tombstone sebagai slot kosong (dapat ditimpa dengan data baru jika kunci tidak ditemukan di sepanjang probe).

### 4. Dynamic Resizing dan Amortized Analysis
Ketika $\alpha$ melampaui ambang batas kritis (umumnya $\alpha \ge 0.7$ untuk Open Addressing, atau $\alpha \ge 0.75$ untuk Chaining):
1. Alokasikan array baru berkapasitas $m' = 2m$ (atau bilangan prima terdekat yang lebih besar dari $2m$).
2. Lakukan iterasi pada seluruh tabel lama.
3. Hitung ulang indeks baru untuk setiap elemen: $i' = h(k) \pmod{m'}$.
4. Deallokasi tabel lama.

Operasi tunggal ini memakan waktu $O(n)$, namun karena hanya dipicu setiap kali kapasitas array digandakan, rata-rata biaya operasi penyisipan teramortisasi tetap berada pada **$O(1)$**.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Mekanisme Probing dan Tombstone pada Open Addressing

```
Array Kapasitas m = 8
Fungsi Hash Sederhana: h(k) = k % 8

Tahap 1: Insert Kunci 16, 24, 32 (Linear Probing: step + 1)
  h(16) = 0 -> Simpan di [0]
  h(24) = 0 -> Kolisi di [0] -> Cek [1] (Kosong) -> Simpan di [1]
  h(32) = 0 -> Kolisi di [0], Kolisi di [1] -> Cek [2] (Kosong) -> Simpan di [2]

   Slot Index:   [0]      [1]      [2]      [3]      [4]      [5]      [6]      [7]
               ┌────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┐
   State:      │ Key:16 │ Key:24 │ Key:32 │ EMPTY  │ EMPTY  │ EMPTY  │ EMPTY  │ EMPTY  │
               └────────┴────────┴────────┴────────┴────────┴────────┴────────┴────────┘

───────────────────────────────────────────────────────────────────────────────────

Tahap 2: Delete Kunci 24 (Salah vs Benar)

  PENDEKATAN SALAH (Set to EMPTY):
   Slot Index:   [0]      [1]      [2]      [3]
               ┌────────┬────────┬────────┬────────┐
   State:      │ Key:16 │ EMPTY  │ Key:32 │ EMPTY  │
               └────────┴────────┴────────┴────────┘
   * Lookup Key 32: h(32)=0. Cek [0] (Mismatch). Cek [1] (EMPTY). 
     Algoritma berhenti dan mengembalikan NOT_FOUND! (Padahal 32 ada di [2]).

  PENDEKATAN BENAR (TOMBSTONE):
   Slot Index:   [0]      [1]      [2]      [3]
               ┌────────┬────────┬────────┬────────┐
   State:      │ Key:16 │  «DEL» │ Key:32 │ EMPTY  │
               └────────┴────────┴────────┴────────┘
   * Lookup Key 32: h(32)=0. Cek [0] (Mismatch). Cek [1] («DEL» -> Lanjut Probing!).
     Cek [2] -> Match! Key 32 ditemukan.

───────────────────────────────────────────────────────────────────────────────────

Tahap 3: Insert Kunci 40 (h(40) = 0)
   - Probing: [0] terisi (Key:16).
   - Probing: [1] adalah «DEL» (Catat slot 1 sebagai first_available_slot).
   - Probing: [2] terisi (Key:32).
   - Probing: [3] adalah EMPTY (Konfirmasi bahwa 40 memang belum ada di tabel).
   - Tulis Key:40 ke first_available_slot, yaitu slot [1].

   Slot Index:   [0]      [1]      [2]      [3]
               ┌────────┬────────┬────────┬────────┐
   State:      │ Key:16 │ Key:40 │ Key:32 │ EMPTY  │
               └────────┴────────┴────────┴────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Implementasi dasar Hash Table menggunakan **Separate Chaining** untuk memahami alokasi array of linked lists tanpa resizing dinamis.

```python
from typing import Any, Optional

class Node:
    """Elemen node untuk linked list pada bucket chaining."""
    def __init__(self, key: Any, value: Any):
        self.key: Any = key
        self.value: Any = value
        self.next: Optional[Node] = None

class SimpleChainingHashTable:
    def __init__(self, capacity: int = 7):
        self.capacity: int = capacity
        # Menginisialisasi bucket array dengan referensi None
        self.buckets: list[Optional[Node]] = [None] * self.capacity

    def _hash(self, key: Any) -> int:
        """Menghitung indeks bucket berbasis hash integer built-in."""
        return hash(key) % self.capacity

    def put(self, key: Any, value: Any) -> None:
        index = self._hash(key)
        head = self.buckets[index]

        # Cek jika key sudah ada, lakukan update
        current = head
        while current is not None:
            if current.key == key:
                current.value = value
                return
            current = current.next

        # Jika key tidak ada, sisipkan node baru di awal list (head insertion: O(1))
        new_node = Node(key, value)
        new_node.next = self.buckets[index]
        self.buckets[index] = new_node

    def get(self, key: Any) -> Any:
        index = self._hash(key)
        current = self.buckets[index]
        while current is not None:
            if current.key == key:
                return current.value
            current = current.next
        raise KeyError(f"Key '{key}' tidak ditemukan.")

    def delete(self, key: Any) -> None:
        index = self._hash(key)
        current = self.buckets[index]
        prev: Optional[Node] = None

        while current is not None:
            if current.key == key:
                if prev is None:
                    self.buckets[index] = current.next
                else:
                    prev.next = current.next
                return
            prev = current
            current = current.next
        raise KeyError(f"Key '{key}' tidak ditemukan.")

# Verifikasi Alur
if __name__ == "__main__":
    ht = SimpleChainingHashTable(capacity=5)
    ht.put("Alpha", 100)
    ht.put("Beta", 200)
    # Paksa kolisi jika hash(key) menghasilkan index sama
    print(f"Alpha: {ht.get('Alpha')}")
    print(f"Beta: {ht.get('Beta')}")
    ht.delete("Alpha")
    try:
        ht.get("Alpha")
    except KeyError:
        print("Alpha berhasil dihapus.")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi tingkat produksi dari **Open Addressing Hash Map** dengan skema **Linear Probing**, penanganan penanda **Tombstone**, rasio **Load Factor**, dan operasi **Rehashing Dinamis**.

```python
from typing import Any, Optional

class _Entry:
    __slots__ = ('key', 'value')
    def __init__(self, key: Any, value: Any):
        self.key: Any = key
        self.value: Any = value

class ProductionOpenAddressingHashMap:
    # Objek singleton unik untuk penanda slot terhapus
    _TOMBSTONE = object()

    def __init__(self, initial_capacity: int = 8, load_factor_threshold: float = 0.65):
        if initial_capacity < 4:
            initial_capacity = 4
        self._capacity: int = initial_capacity
        self._load_factor_threshold: float = load_factor_threshold
        self._table: list[Any] = [None] * self._capacity
        self._size: int = 0          # Jumlah key-value aktif
        self._tombstones: int = 0    # Jumlah slot yang ditandai terhapus

    def _hash(self, key: Any) -> int:
        """Menggunakan hash internal dan memetakan dengan bitmask jika capacity = 2^k,
        atau modulo m untuk general purpose."""
        # Menambahkan bit-shifting sederhana untuk mengurangi pola clustering buruk
        h = hash(key)
        h ^= (h >> 16)
        return h & (self._capacity - 1) if (self._capacity & (self._capacity - 1)) == 0 else h % self._capacity

    @property
    def load_factor(self) -> float:
        # Kapasitas yang terpakai dihitung dari entry aktif + tombstones
        return (self._size + self._tombstones) / self._capacity

    def put(self, key: Any, value: Any) -> None:
        if key is None:
            raise ValueError("Kunci tidak boleh bernilai None.")

        if self.load_factor >= self._load_factor_threshold:
            self._resize(self._capacity * 2)

        idx = self._hash(key)
        first_tombstone_idx: Optional[int] = None

        while self._table[idx] is not None:
            if self._table[idx] is self._TOMBSTONE:
                if first_tombstone_idx is None:
                    first_tombstone_idx = idx
            elif self._table[idx].key == key:
                # Key sudah ada; lakukan update value secara in-place
                self._table[idx].value = value
                return
            idx = (idx + 1) % self._capacity

        # Jika key tidak ada, sisipkan pada tombstone pertama yang ditemui (reuse space),
        # atau pada slot kosong terminal.
        target_idx = first_tombstone_idx if first_tombstone_idx is not None else idx
        
        if first_tombstone_idx is not None:
            self._tombstones -= 1
            
        self._table[target_idx] = _Entry(key, value)
        self._size += 1

    def get(self, key: Any) -> Any:
        idx = self._hash(key)
        while self._table[idx] is not None:
            if self._table[idx] is not self._TOMBSTONE:
                if self._table[idx].key == key:
                    return self._table[idx].value
            idx = (idx + 1) % self._capacity
        raise KeyError(f"Key '{key}' tidak ditemukan di dalam Hash Table.")

    def remove(self, key: Any) -> Any:
        idx = self._hash(key)
        while self._table[idx] is not None:
            if self._table[idx] is not self._TOMBSTONE:
                if self._table[idx].key == key:
                    removed_val = self._table[idx].value
                    self._table[idx] = self._TOMBSTONE
                    self._size -= 1
                    self._tombstones += 1
                    return removed_val
            idx = (idx + 1) % self._capacity
        raise KeyError(f"Key '{key}' tidak ditemukan untuk dihapus.")

    def _resize(self, new_capacity: int) -> None:
        old_table = self._table
        self._capacity = new_capacity
        self._table = [None] * self._capacity
        self._size = 0
        self._tombstones = 0

        for slot in old_table:
            if slot is not None and slot is not self._TOMBSTONE:
                self.put(slot.key, slot.value)

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        items = []
        for slot in self._table:
            if slot is not None and slot is not self._TOMBSTONE:
                items.append(f"{slot.key!r}: {slot.value!r}")
        return "{" + ", ".join(items) + "}"
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Parameter | Closed Addressing (Separate Chaining) | Open Addressing (Linear Probing) | Open Addressing (Double Hashing) |
| :--- | :--- | :--- | :--- |
| **Spatial Cache Locality** | **Sangat Rendah:** Linked list node terfragmentasi di berbagai blok heap memori. | **Sangat Tinggi:** Akses sequential array memanfaatkan cache line hardware secara maksimal. | **Moderat:** Akses berbasis step size konstan dapat menyebabkan cache misses lebih sering dari linear. |
| **Batas Load Factor ($\alpha$)** | **Fleksibel:** Dapat beroperasi normal bahkan ketika $\alpha > 1.0$. | **Ketat:** Performa hancur seketika jika $\alpha \ge 0.7 - 0.8$. Wajib di-resize. | **Ketat:** Membutuhkan $\alpha < 0.8$, tetapi lebih resisten terhadap clustering dibanding linear. |
| **Overhead Memori per Entry** | **Tinggi:** Memerlukan alokasi pointer ekstra (`sizeof(pointer)`) untuk setiap node individual. | **Nol Overhead Node:** Hanya membutuhkan array buffer internal yang sedikit lebih besar. | **Nol Overhead Node:** Hanya membutuhkan array buffer internal. |
| **Sensitivitas Fungsi Hash** | **Rendah:** Kolisi hanya memperpanjang traversal rantai list lokal. | **Sangat Tinggi:** Distribusi hash yang buruk langsung memicu efek snowball (Primary Clustering). | **Moderat-Tinggi:** Memerlukan dua fungsi hash yang saling independen dan memenuhi syarat prima. |
| **Kompleksitas Deletion** | **Trivial:** Penghapusan node linked list konvensional pointer dereference. | **Kompleks:** Wajib mengelola state `Tombstone` atau melakukan *shift-back rehash*. | **Kompleks:** Wajib mengelola state `Tombstone`. |

---

## SEKSI 11 — BEST PRACTICES

1. **Pemilihan Dimensi Array (Power of Two vs Bilangan Prima):**
   * Jika menggunakan fungsi hash non-kriptografis modern (misal: xxHash, MurmurHash3), gunakan kapasitas $m = 2^k$. Modulo dihitung via bitwise AND: `hash & (m - 1)`, yang berjalan dalam 1 siklus CPU.
   * Jika menggunakan fungsi hash ad-hoc atau sederhana, gunakan ukuran array berupa **bilangan prima**. Modulo bilangan prima mendistribusikan pola numerik yang berulang jauh lebih baik dibanding modulo genap.
2. **Mitigasi Hash DoS (Denial of Service):**
   * Untuk input yang berasal dari external/untrusted network (misal: query parameter HTTP API), jangan gunakan fungsi hash standar deterministik bahasa pemrograman (seperti `siphash` non-seeded). Gunakan hash beralgoritma **SipHash** dengan cryptographic random seed unik per instance proses.
3. **Thresholding Load Factor:**
   * Batasi $\alpha$ pada $0.65 - 0.70$ untuk skema *Open Addressing*. Melampaui $0.75$ memicu *exponential probing length*.
   * Batasi $\alpha$ pada $0.75 - 1.0$ untuk skema *Separate Chaining*.
4. **Optimasi Struktur Node pada Separate Chaining:**
   * Jangan gunakan linked list murni jika data per bucket berpotensi besar. Terapkan konversi dinamis (seperti Java 8+ HashMap): Ubah linked list menjadi Red-Black Tree jika elemen dalam satu bucket $\ge 8$, membatasi skenario terburuk dari $O(n)$ ke $O(\log n)$.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menggunakan Kunci yang Bersifat Mutable (Dapat Berubah)
```python
# KESALAHAN FATAL
data = {}
my_list = [1, 2, 3] # List bersifat mutable
# Python mencegah ini dengan error: TypeError: unhashable type: 'list'
# Namun, objek custom class sering kali memiliki implementasi hash cacat:

class Entity:
    def __init__(self, uid: int, name: str):
        self.uid = uid
        self.name = name
    def __hash__(self):
        return hash(self.name) # Bergantung pada variabel mutable

e = Entity(101, "Alice")
ht[e] = "Profile Data"
e.name = "Bob" # Hash value berubah drastis di memori!
# print(ht[e]) -> KeyError! Key hilang secara permanen di dalam tabel.
```
*Aturan:* Kunci hash map **wajib bersifat immutable** sepanjang siklus hidupnya (misal: integer, string, tuple immutable, atau UUID).

### 2. Mengosongkan Slot secara Langsung (`None`) saat Delete pada Open Addressing
Mengosongkan slot yang dihapus memutus probing sequence pencarian entri lain yang mengalami kolisi dan tergeser setelah slot tersebut. Hal ini menciptakan *silent bug* di mana data yang ada di dalam tabel tidak dapat ditemukan kembali (*false negative*).

### 3. Mengabaikan Siklus pada Quadratic Probing
Jika formula konstanta quadratic probing tidak dikonfigurasi secara matematis ($c_1, c_2$), algoritma dapat terjebak dalam *infinite loop* saat mencari slot kosong, meskipun tabel belum penuh ($\alpha < 1$).
*Aturan Teorema:* Untuk kapasitas $m = 2^k$, formula $h(k, i) = (h(k) + \frac{i + i^2}{2}) \pmod m$ menjamin seluruh slot array akan dikunjungi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Implementasi Count-Frequency Token (Tingkat: Mudah)
**Instruksi:** Buat fungsi pemrosesan teks yang memanfaatkan `ProductionOpenAddressingHashMap` yang telah dibuat pada Seksi 09 untuk menghitung frekuensi kemunculan setiap kata dalam korpus teks berikut tanpa menggunakan library bawaan Python `collections.Counter` atau dictionary standar.

```python
corpus = "apple banana apple cherry date banana apple banana cherry fig"
# Tulis logika tokenisasi dan akumulasi frekuensi menggunakan custom hash map.
```

### Latihan 2: Implementasi Tombstone Compaction (Tingkat: Menengah)
**Instruksi:** Pada `ProductionOpenAddressingHashMap`, jika terjadi siklus `put` dan `remove` berulang kali, tabel dapat dipenuhi oleh `Tombstone` meskipun jumlah elemen aktif ($\text{size}$) relatif kecil. Hal ini memicu resizing yang tidak efisien.
* Tugas: Modifikasi kelas tersebut untuk mendukung metode `_compact_tombstones()` yang membersihkan tombstone dan mengonsolidasi tabel tanpa menggandakan kapasitas jika:
  $$\frac{\text{tombstones}}{\text{capacity}} > 0.3 \quad \text{dan} \quad \frac{\text{size}}{\text{capacity}} < 0.4$$

### Latihan 3: Implementasi Robin Hood Hashing (Tingkat: Mahir)
**Instruksi:** Rancang modifikasi Open Addressing dengan varian **Robin Hood Hashing**.
* Konsep Inti: Saat melakukan `put`, jika probe sequence length (PSL) dari entri baru lebih besar daripada PSL dari entri yang saat ini menempati slot, *swap* (curi) slot tersebut dari entri yang "kaya" dan berikan kepada entri baru yang "miskin". Lanjutkan probing untuk menyisipkan kembali entri yang tergeser.
* Tujuannya adalah meminimalkan variansi panjang probing di seluruh tabel.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

**1. Jika sebuah hash table dengan Open Addressing menggunakan kapasitas $m = 100$ dan saat ini menampung $n = 70$ elemen aktif serta $20$ tombstones, berapa effective load factor yang menentukan waktu untuk melakukan rehash?**
* A. 0.70
* B. 0.90
* C. 0.20
* D. 0.50
* *Jawaban:* **B**. *Penjelasan:* Untuk open addressing, slot yang ditempati oleh tombstone tidak dapat digunakan secara langsung untuk pencarian tanpa probing, sehingga efektivitas probing slot yang terpakai adalah $(n + \text{tombstones}) / m = (70 + 20) / 100 = 0.90$. Jika rehash tidak dilakukan, efisiensi pencarian akan drop drastis.

**2. Mengapa Separate Chaining lebih unggul dibanding Linear Probing pada lingkungan memory-constrained di mana nilai Load Factor diperbolehkan melewati 1.0?**
* A. Karena Separate Chaining tidak menggunakan pointer memori.
* B. Karena Linear Probing secara matematis mustahil menampung lebih dari $m$ elemen ($\alpha \le 1.0$).
* C. Karena Separate Chaining memiliki spatial cache locality yang lebih baik.
* D. Karena Linear Probing membutuhkan CPU hardware floating point unit.
* *Jawaban:* **B**. *Penjelasan:* Open addressing menyimpan seluruh data langsung di dalam slot array fisik $m$. Sesuai prinsip Sarang Merpati, open addressing tidak dapat menampung elemen saat $n > m$ ($\alpha > 1.0$), sedangkan Chaining dapat menampung elemen tak terbatas melalui link list sekunder.

**3. Fenomena di mana beberapa kunci berbeda menghasilkan indeks awal yang sama dan kemudian mengeksekusi step probe identik yang memperburuk degradasi kinerja disebut:**
* A. Primary Clustering
* B. Secondary Clustering
* C. Avalanche Degradation
* D. Cyclic Probing
* *Jawaban:* **B**. *Penjelasan:* Secondary clustering terjadi ketika kunci yang memiliki nilai hash basis sama mengikuti sekuens probing yang sama (umum terjadi pada Quadratic Probing). Primary clustering terjadi pada linear probing di mana blok-blok probing yang berbeda saling bergabung membentuk klaster besar.

**4. Mengapa operasi bitwise AND `h & (m - 1)` hanya valid untuk perhitungan indeks array jika $m$ bernilai eksak $2^k$?**
* A. Karena bilangan pangkat dua selalu berakhiran bit nol.
* B. Karena $2^k - 1$ membentuk bitmask biner bernilai `1` pada seluruh $k$ bit terendah, mereplikasi fungsi modulo $2^k$.
* C. Karena compiler assembly tidak dapat mengeksekusi instruksi pembagian.
* D. Karena modulo bilangan ganjil selalu lambat.
* *Jawaban:* **B**. *Penjelasan:* Secara biner, $2^k - 1$ adalah representasi angka dengan $k$ buah bit 1 (misal $8 - 1 = 7 = 0111_2$). Operasi bitwise AND dengan mask ini memotong bit di atas $k$, yang setara secara matematis dengan `h % (2^k)`.

**5. Manakah fungsi hash berikut yang TIDAK direkomendasikan untuk struktur data hash table in-memory berkecepatan tinggi karena tingginya siklus CPU yang dibutuhkan?**
* A. xxHash
* B. MurmurHash3
* C. SHA-256
* D. FNV-1a
* *Jawaban:* **C**. *Penjelasan:* SHA-256 adalah cryptographic hash function yang didesain secara sengaja memiliki kompleksitas matematika tinggi untuk menjamin collision resistance dan preimage resistance. Menggunakannya untuk indeks in-memory hash table akan menciptakan CPU bottleneck masif.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Teks Wajib:**
  * Cormen, T. H., Leiserson, C. E., Rivest, R. L., & Stein, C. (2022). *Introduction to Algorithms* (4th ed.). MIT Press. — **Chapter 11: Hash Tables**.
  * Knuth, D. E. (1998). *The Art of Computer Programming, Volume 3: Sorting and Searching* (2nd ed.). Addison-Wesley. — **Section 6.4: Hashing**.
* **Makalah Akademis & Standar Arsitektur:**
  * Celis, P. (1986). *Robin Hood Hashing*. University of Waterloo Technical Report.
  * Aumasson, J. P., & Bernstein, D. J. (2012). *SipHash: a fast short-input PRF*. In INDOCRYPT 2012. (Membahas pencegahan serangan Hash-DoS pada web infrastructure).
* **Repositori & Dokumentasi Engine:**
  * Columbo, Y. et al. *xxHash - Extremely fast non-cryptographic hash algorithm*. [https://github.com/Cyan4973/xxHash](https://github.com/Cyan4973/xxHash).
  * CPython Implementation Details of `dict` (Compact Hash Tables): [Objects/dictobject.c](https://github.com/python/cpython/blob/main/Objects/dictobject.c).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **Hashing** mentransformasikan kunci arbitrer berukuran tak terhingga menjadi indeks array berdimensi tetap menggunakan fungsi hash deterministik untuk mencapai kompleksitas rata-rata $O(1)$ untuk operasi Search, Insert, dan Delete.
* Berdasarkan prinsip sarang merpati, **kolisi hash pasti terjadi** pada himpunan data dinamis, memerlukan arsitektur mitigasi kolisi terencana.
* **Separate Chaining** menangani kolisi menggunakan struktur data terhubung di luar array, memberikan fleksibilitas tinggi pada kondisi memori padat ($\alpha > 1.0$), namun membayar penalti pada *cache misses* dan alokasi pointer.
* **Open Addressing** mengonsolidasikan semua pasangan key-value langsung di array utama menggunakan *Probing sequences*. Pendekatan ini unggul dalam kecepatan akses cache perangkat keras, tetapi memerlukan penanganan status khusus (**Tombstones**) saat operasi *Delete* dan batas **Load Factor** yang ketat ($\alpha < 0.7$).
* Performa konstan $O(1)$ Hash Table hanya dapat dipertahankan melalui **Dynamic Rehashing** berkala saat rasio $\alpha$ menyentuh limit batas saturasi.

---

## SEKSI 17 — GLOSARIUM

* **Avalanche Effect:** Perilaku matematis fungsi hash di mana fluktuasi minimal satu bit pada data input akan menghasilkan transformasi masif (rata-rata 50% bit berubah) pada representasi output.
* **Closed Addressing:** Metodologi resolusi kolisi di mana elemen-elemen yang bertubrukan disimpan di luar tabel array inti (misal: linked list per bucket).
* **Load Factor ($\alpha$):** Parameter metrik saturasi hash table yang didefinisikan sebagai rasio jumlah elemen tersimpan dibagi kapasitas total bucket array ($\alpha = n/m$).
* **Open Addressing:** Metodologi resolusi kolisi di mana seluruh record data disimpan langsung di dalam slot array bucket melalui eksplorasi alamat berurutan (probing).
* **Primary Clustering:** Fenomena pembentukan kelompok slot terisi yang saling menyambung pada teknik Linear Probing, memicu degradasi performa ke arah linear $O(n)$.
* **Rehashing:** Proses realokasi ukuran kapasitas memori array bucket (biasanya penggandaan ukuran) yang diikuti oleh komputasi ulang lokasi seluruh kunci lama ke array baru.
* **Tombstone:** Marker biner/objek sentinel khusus pada Open Addressing yang mengindikasikan bahwa suatu slot telah dihapus guna mencegah terputusnya probe chain entri berikutnya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi:** Pastikan peserta didik memahami dengan jelas **mengapa** kita membutuhkan `Tombstone` pada Open Addressing. Lakukan demonstrasi live-coding tanpa tombstone terlebih dahulu: hapus sebuah elemen di tengah probing chain, lalu tunjukkan bagaimana lookup terhadap elemen berikutnya gagal. Hal ini secara instan mengunci pemahaman konsep.
* **Eksperimen Hardware Cache:** Jika kelas menggunakan bahasa tingkat rendah (C/C++ atau Rust), sediakan benchmark perbandingan traversal 1.000.000 elemen antara chaining array-of-pointers vs flat-array open addressing untuk mendemonstrasikan fenomena *L1/L2 data cache misses* secara nyata.
* **Perangkap Pembelajaran:** Peserta didik sering kali salah mengira bahwa fungsi hash kriptografis (seperti SHA-256) selalu lebih superior dibanding non-kriptografis. Tekankan secara eksplisit disparitas kecepatan instruksi CPU antara keduanya dalam konteks in-memory data structures.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2026):**
  * Rilis inisial materi Bab 04 Modul 01.
  * Standarisasi format 20 seksi teknis GEMINI.md.
  * Penambahan implementasi produksi Open Addressing Linear Probing lengkap dengan tombstone reuse mechanics.
  * Integrasi modul mitigasi keamanan arsitektur (Hash DoS & SipHash context).

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `CS-DSA-03-03` — Skip Lists: Probabilistic Alternative to Balanced Trees
* **Modul Berikutnya:** `CS-DSA-04-02` — Probabilistic Data Structures: Bloom Filter & Counting Bloom Filter
* **Indeks Modul Keseluruhan:** `CS-DSA-INDEX` — Curriculum Map: Data Structures and Algorithms Master Track