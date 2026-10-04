# BAB 10: Algoritma Advanced & Sistem Terdistribusi
## MODUL 01: Consistent Hashing & Virtual Nodes (Hashing Konsisten & Partisi Terdistribusi)

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Kurikulum:** `DSA-01-CF-10-01`
* **Kategori:** `01-Core-Foundations`
* **Jalur Pembelajaran:** *Data Structures, Algorithms & Distributed Architecture*
* **Tingkat Kesulitan:** Advanced
* **Prasyarat:** 
  * Pemahaman mendalam tentang Struktur Data Hash Table & Fungsi Hash (Modul 04-01).
  * Algoritma Pencarian Biner (*Binary Search*) & Red-Black Tree / Binary Search Tree (Modul 05-02).
  * Kompleksitas Waktu & Ruang Asimptotik ($O$-Notation).
* **Estimasi Waktu Belajar:** 4–6 Jam (Teori, Implementasi, dan Analisis Simulasi)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Mendiagnosis** kegagalan partisi data berbasis modulo tradisional ($hash(key) \pmod N$) pada skenario penambahan atau pengurangan simpul (*horizontal scaling*).
2. **Menganalisis** prinsip topologi cincin (*hash ring*) dan membuktikan secara matematis efisiensi migrasi data $O(K/N)$ menggunakan algoritma Consistent Hashing.
3. **Mengimplementasikan** struktur data *Consistent Hash Ring* berbasis pencarian biner dengan kompensasi *Virtual Nodes* (*vnodes*) untuk mengeliminasi skewness/hotspot data.
4. **Mengevaluasi** performa distribusi beban kerja (standar deviasi data) antar simpul fisik dengan variasi kuantitas *virtual nodes*.
5. **Merancang** subsistem partisi dan replikasi kunci (*data partition & replication layer*) untuk sistem penyimpanan terdistribusi berkinerja tinggi.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [Sistem Terdistribusi Multi-Node]
                                           │
                       Menghadapi Masalah Partisi Data & Skalabilitas
                                           │
         ┌─────────────────────────────────┴─────────────────────────────────┐
         ▼                                                                   ▼
[Partisi Modulo Tradisional]                                        [Consistent Hashing]
  - Formula: hash(k) % N                                              - Topologi: Cincin Sirkular [0, 2^32 - 1]
  - Penambahan node: reshuffle O(K)                                  - Penambahan node: migrasi O(K/N)
  - Cache stampede & cascading failure                                - Penempatan: Searah jarum jam (Clockwise)
                                                                             │
                                                                   Mengatasi Non-Uniformity
                                                                             │
                                                                             ▼
                                                                      [Virtual Nodes]
                                                                - Multi-mapping Simpul Fisik
                                                                - Mengurangi Varians & Hotspot
                                                                - Struktur: Binary Search Array / BST
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam arsitektur *monolithic*, penentuan alokasi data ke dalam ember (*bucket*) penyimpanan cukup menggunakan fungsi:

$$\text{Index} = \text{hash}(\text{key}) \pmod N$$

di mana $N$ adalah jumlah server atau partisi yang tersedia. Pendekatan ini bekerja optimal selama nilai $N$ bernilai konstan. Namun, pada arsitektur sistem terdistribusi skala besar (*large-scale distributed storage/caching* seperti Redis Cluster, Apache Cassandra, DynamoDB, Akamai CDN), nilai $N$ bersifat dinamis:
1. Server baru ditambahkan untuk merespons lonjakan beban (*scale-out*).
2. Server mengalami kegagalan perangkat keras atau terputus dari jaringan (*network partition*).
3. Server dinonaktifkan sementara untuk pemeliharaan berkala (*rolling update*).

Ketika $N$ berubah dari $N$ menjadi $N+1$ atau $N-1$, nilai pembagi dari operasi modulo berubah total. Dampaknya, hampir **100% kunci yang tersimpan akan terpetakan ke indeks baru**:

$$\text{Persentase Kunci Berpindah} = \frac{N}{N + 1} \approx 100\% \quad (\text{untuk } N \gg 1)$$

Peristiwa ini memicu *Cache Stampede*: jutaan kueri mendadak meleset (*cache miss*), membebani basis data relasional di belakangnya hingga menyebabkan kegagalan bertingkat (*cascading failure*). Diperlukan algoritma partisi yang membatasi migrasi data hanya pada skala $K/N$ (di mana $K$ adalah total kunci), sehingga sistem terdistribusi dapat menambah atau mengurangi kapasitas secara elastis tanpa degradasi performa.

---

## SEKSI 05 — APA ITU (WHAT)

**Consistent Hashing** adalah teknik partisi data berbasis algoritma di mana ruang keluaran fungsi hash dipetakan ke dalam bentuk lingkaran tertutup (*ring topology*). Pertama kali diperkenalkan secara akademis oleh Karger et al. di MIT pada tahun 1997, algoritma ini menjamin bahwa ketika sebuah simpul ditambahkan atau dihapus dari sistem, rata-rata jumlah kunci yang harus dipindahkan atau dipetakan ulang hanyalah:

$$\Delta K = \frac{K}{N}$$

di mana $K$ adalah total pasangan kunci-nilai dan $N$ adalah total simpul yang beroperasi.

### Karakteristik Utama
1. **Ruang Hash Sirkular:** Ruang nilai hash memiliki batas bawah dan atas yang bertemu kembali (misalnya, bilangan bulat 32-bit dari $0$ hingga $2^{32}-1$).
2. **Pemetaan Kunci Searah Jarum Jam (*Clockwise Lookup*):** Kunci data dan alamat simpul fisik di-hash menggunakan fungsi yang sama ke atas cincin. Data dialokasikan ke simpul pertama yang posisinya lebih besar atau sama dengan nilai hash kunci tersebut.
3. **Virtual Nodes (*Vnodes*):** Representasi jamak dari satu simpul fisik pada titik-titik berbeda di cincin hash. Tujuannya adalah mendistribusikan beban secara seragam (*uniform balance*) dan mengakomodasi heterogenitas kapasitas perangkat keras (*weighted nodes*).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Pembentukan Cincin (*The Ring Initialization*)
Rentang nilai integer dari fungsi hash (contohnya Murmur3 atau MD5 yang dinormalisasi ke 32-bit) diposisikan secara melingkar:
$$\text{Ring Space} = [0, 2^{32} - 1]$$
Nilai $2^{32}-1$ terhubung secara logis kembali ke indeks $0$.

### 2. Registrasi Simpul Fisik & Virtual Nodes
Setiap simpul fisik $S_i$ didaftarkan ke dalam cincin melalui sejumlah $V$ replika virtual. Setiap virtual node di-hash secara unik, misalnya dengan konvensi penamaan:
$$\text{Token}_{i, j} = \text{hash}(\text{NodeID}_i + \text{"\#"} + j) \quad \text{untuk } j \in [0, V-1]$$
Semua token yang dihasilkan disimpan dalam struktur data terurut (seperti *Sorted Array* atau *Self-Balancing Binary Search Tree*) yang memetakan $\text{Token} \to \text{NodeID}$.

### 3. Penempatan Kunci Data (*Key Mapping*)
Ketika data dengan identifier $k$ disimpan:
1. Hitung nilai hash kunci: $H_k = \text{hash}(k)$.
2. Lakukan pencarian biner (*binary search* atau fungsi `std::upper_bound` / Python `bisect_right`) pada struktur token terurut untuk menemukan token simpul pertama $T$ di mana $T \ge H_k$.
3. Jika $H_k$ lebih besar dari seluruh token yang ada di cincin, kunci tersebut dialokasikan ke token pertama pada cincin (indeks $0$), menyelesaikan siklus sirkular.
4. Identifikasi simpul fisik pemilik token $T$.

```
Kompleksitas Pencarian Simpul Pemilik:
- Menggunakan Array Terurut + Binary Search : O(log(N * V))
- Menggunakan Red-Black Tree              : O(log(N * V))
Di mana N = Jumlah Simpul Fisik, V = Jumlah Virtual Node per Simpul.
```

### 4. Skalabilitas: Penambahan Simpul Baru
Jika simpul fisik baru $S_{new}$ bergabung ke jaringan dengan sejumlah $V$ token:
1. Token-token baru disisipkan ke dalam cincin terurut.
2. Simpul $S_{new}$ hanya mengambil alih kepemilikan kunci dari simpul tetangga searah jarum jam (*successor*) pada segmen busur yang terintersepsi oleh token barunya.
3. Simpul-simpul lain yang tidak bersebelahan dengan busur token baru tidak mengalami pemindahan data sama sekali.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Topologi Hash Ring Dasar (Tanpa Virtual Nodes)

```
                       0 / 2^32-1
                     .---''''---.
                  .-'            '-.
                .'                  '.
               /   [Node A: 100]      \
              /                        \
             |                          |
    Key 1    |                          |    [Node B: 1500]
 (hash: 350) |                          |   /
      \      ;                          ;  /
       '-->   \                        / <-'
               \                      /
                '.                  .'  <-- Key 2 (hash: 2200)
                  '-.            .-'
                     '---....---'
                     [Node C: 2500]

Alokasi:
- Key 1 (hash: 350)  --> Bergerak searah jarum jam --> Menuju Node B (1500)
- Key 2 (hash: 2200) --> Bergerak searah jarum jam --> Menuju Node C (2500)
```

---

### Diagram 2: Penambahan Simpul & Minimalisasi Migrasi Data

```
KONDISI AWAL (Node A & Node B):
                      [Node A: 1000]
                      /            \
                     /              \
         [Key X: 800]                [Key Y: 1500]
         (Dialokasikan ke A)          (Dialokasikan ke B)
                     \              /
                      \            /
                      [Node B: 2000]

PENAMBAHAN NODE C PADA POSISI 1200:
                      [Node A: 1000]
                      /     |      \
                     /      |       \
         [Key X: 800]       |        [Node C: 1200]  <-- BARU
         (Tetap di A)       |              \
                            |               [Key Y: 1500]
                            |               (Tetap di B)
                            \              /
                             [Node B: 2000]

Analisis Migrasi:
- Key X (800) tetap pada Node A (karena 800 <= 1000).
- Key Y (1500) tetap pada Node B (karena 1500 <= 2000).
- HANYA kunci di interval (1000, 1200] yang berpindah dari Node B ke Node C!
```

---

### Diagram 3: Virtual Nodes untuk Distribusi Beban Merata

```
Simpul Fisik : Node A (Merah), Node B (Biru)
Vnodes (3 per node) : A-0, A-1, A-2 | B-0, B-1, B-2

                      0 / 2^32-1
                    .---''A-0''---.
                 .-'               '-.
             B-2'                     'B-0
             /                           \
            |                             |
           A-2                           A-1
            |                             |
             \                           /
              '-.                     .-'
                 '-.               .-'
                    '---..B-1..--'

Keuntungan: Ruang cincin terpecah menjadi segmen-segmen kecil yang saling bersilangan.
Peluang sebuah simpul mendapatkan rentang busur raksasa (*hotspot segment*) ditekan secara drastis.
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi konseptual *Consistent Hash Ring* dasar tanpa dependensi eksternal, mendemonstrasikan algoritma pencarian biner langsung pada list cincin.

```python
import bisect
import hashlib
from typing import List, Optional

class SimpleConsistentHash:
    def __init__(self):
        # Ring menyimpan representasi hash dari node dalam keadaan terurut
        self.ring: List[int] = []
        # Mapping dari hash token ke identifier node fisik
        self.node_map: dict[int, str] = {}

    def _hash(self, key: str) -> int:
        """Memetakan string input ke integer 32-bit menggunakan SHA-256."""
        digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
        # Mengambil 8 karakter pertama untuk representasi 32-bit integer
        return int(digest[:8], 16)

    def add_node(self, node: str) -> None:
        """Menambahkan simpul fisik ke dalam cincin."""
        node_hash = self._hash(node)
        if node_hash in self.node_map:
            return  # Mencegah tabrakan identik
        
        # Masukkan hash ke array terurut (O(N) untuk insersi array, O(log N) untuk bisect)
        idx = bisect.bisect_right(self.ring, node_hash)
        self.ring.insert(idx, node_hash)
        self.node_map[node_hash] = node

    def remove_node(self, node: str) -> None:
        """Menghapus simpul fisik dari cincin."""
        node_hash = self._hash(node)
        if node_hash not in self.node_map:
            return
        
        self.ring.remove(node_hash)
        del self.node_map[node_hash]

    def get_node(self, key: str) -> Optional[str]:
        """Mengambil node penanggung jawab key dengan pencarian searah jarum jam."""
        if not self.ring:
            return None

        key_hash = self._hash(key)
        # Binary search untuk menemukan node dengan token >= key_hash
        idx = bisect.bisect_right(self.ring, key_hash)

        # Jika key_hash melampaui elemen terbesar cincin, bungkus kembali ke indeks 0
        if idx == len(self.ring):
            idx = 0

        return self.node_map[self.ring[idx]]

# Uji Coba Sederhana
if __name__ == "__main__":
    ch = SimpleConsistentHash()
    for s in ["192.168.1.10", "192.168.1.11", "192.168.1.12"]:
        ch.add_node(s)

    kunci_sampel = ["user:101", "user:102", "order:992", "session:xyz"]
    for k in kunci_sampel:
        print(f"Kunci '{k}' dialokasikan ke Node: {ch.get_node(k)}")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi tingkat produksi membutuhkan dukungan **Virtual Nodes**, fungsi hash non-kriptografis berkecepatan tinggi (*high performance non-cryptographic hashing*), dukungan replikasi data (*multi-node replication*), serta analisis metrik distribusi beban.

Berikut kode lengkap Python 3 yang mereplikasi mekanisme partisi ala Apache Cassandra/Amazon Dynamo:

```python
import bisect
import mmh3  # MurmurHash3 (Non-cryptographic, cepat, distribusi bit seragam)
import statistics
from typing import Dict, List, Set, Tuple

class ProductionConsistentHashRing:
    def __init__(self, replicas: int = 150):
        """
        :param replicas: Jumlah virtual node per simpul fisik (Vnodes).
                         100-250 adalah nilai ideal menurut penelitian Dynamo.
        """
        self.replicas: int = replicas
        self.ring: List[int] = []  # Sorted array of token hashes
        self.token_to_node: Dict[int, str] = {}  # Map: Token Hash -> Node Fisik
        self.nodes: Set[str] = set()  # Himpunan unik simpul fisik

    def _hash(self, val: str) -> int:
        """Menghasilkan representasi integer tak bertanda (unsigned 32-bit integer)."""
        return mmh3.hash(val, signed=False)

    def add_node(self, node: str) -> None:
        """Mendaftarkan node fisik dan menginjeksi virtual nodes ke cincin."""
        if node in self.nodes:
            return
        self.nodes.add(node)

        for i in range(self.replicas):
            vnode_id = f"{node}#vn-{i}"
            token = self._hash(vnode_id)
            
            # Mempertahankan status array terurut via binary insertion
            idx = bisect.bisect_right(self.ring, token)
            self.ring.insert(idx, token)
            self.token_to_node[token] = node

    def remove_node(self, node: str) -> None:
        """Menghapus node fisik dan memusnahkan seluruh virtual nodes miliknya."""
        if node not in self.nodes:
            return
        self.nodes.remove(node)

        tokens_to_remove = set()
        for i in range(self.replicas):
            vnode_id = f"{node}#vn-{i}"
            token = self._hash(vnode_id)
            tokens_to_remove.add(token)

        # Konstruksi ulang ring dengan token yang tersisa
        self.ring = [t for t in self.ring if t not in tokens_to_remove]
        for t in tokens_to_remove:
            self.token_to_node.pop(t, None)

    def get_preference_list(self, key: str, n_replicas: int) -> List[str]:
        """
        Mengambil N simpul fisik UNIK berbeda untuk skenario replikasi data
        (Preference List ala DynamoDB).
        """
        if not self.ring:
            return []
        
        n_replicas = min(n_replicas, len(self.nodes))
        key_hash = self._hash(key)
        start_idx = bisect.bisect_right(self.ring, key_hash)
        
        result_nodes: List[str] = []
        visited_nodes: Set[str] = set()
        total_tokens = len(self.ring)

        # Lakukan iterasi cincin searah jarum jam
        for offset in range(total_tokens):
            curr_idx = (start_idx + offset) % total_tokens
            token = self.ring[curr_idx]
            target_node = self.token_to_node[token]

            if target_node not in visited_nodes:
                visited_nodes.add(target_node)
                result_nodes.append(target_node)

            if len(result_nodes) == n_replicas:
                break

        return result_nodes


# =====================================================================
# SIMULASI DISTRIBUSI BEBAN KERJA & STANDAR DEVIASI
# =====================================================================
def run_simulation():
    print("=== SIMULASI CONSISTENT HASH RING & ANALISIS UNIFORMITY ===")
    
    physical_nodes = [f"srv-storage-{i:02d}" for i in range(1, 6)]  # 5 Physical Nodes
    ring = ProductionConsistentHashRing(replicas=200)

    for node in physical_nodes:
        ring.add_node(node)

    # Injeksi 100,000 Keys
    total_keys = 100_000
    load_distribution: Dict[str, int] = {node: 0 for node in physical_nodes}

    for k_id in range(total_keys):
        key = f"customer:payload:{k_id}"
        # Ambil primary node penanggung jawab (1 replica)
        primary_node = ring.get_preference_list(key, n_replicas=1)[0]
        load_distribution[primary_node] += 1

    print(f"Total Keys Didistribusikan: {total_keys:,}")
    print("\nSebaran Kunci per Simpul:")
    for node, count in sorted(load_distribution.items()):
        percentage = (count / total_keys) * 100
        print(f"  [{node}] : {count:,} keys ({percentage:.2f}%)")

    # Hitung Deviasi Standar
    std_dev = statistics.stdev(load_distribution.values())
    mean_val = statistics.mean(load_distribution.values())
    cv = (std_dev / mean_val) * 100  # Koefisien Variasi

    print(f"\nRata-rata Ideal per Node : {mean_val:,.1f}")
    print(f"Standar Deviasi          : {std_dev:,.2f}")
    print(f"Koefisien Variasi (CV)   : {cv:.2f}% (Toleransi sistem produksi < 5-8%)")

    # Uji Coba Preferensi Replikasi
    sample_key = "tx:account:998182"
    replicas = ring.get_preference_list(sample_key, n_replicas=3)
    print(f"\nReplikasi Simpul untuk Kunci '{sample_key}':")
    print(f"  Primary: {replicas[0]}")
    print(f"  Replicas (Backup): {replicas[1:]}")

if __name__ == "__main__":
    run_simulation()
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Parameter / Arsitektur | Consistent Hashing Dasar (No Vnodes) | Consistent Hashing + Vnodes | Modulo Tradisional ($k \bmod N$) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Partisi** | $O(\log N)$ via Binary Search | $O(\log(N \cdot V))$ via Binary Search | **$O(1)$** Operasi Aritmatika Instan |
| **Konsumsi Memori Metadata** | Minimal ($N$ entri token pada router/klien) | Sedang ($N \cdot V$ token disimpan dalam memori) | Nol (Hanya menyimpan nilai skalar $N$) |
| **Migrasi Data saat Scale-Up** | Minimal ($K / N_{baru}$) | Minimal ($K / N_{baru}$) | **Bencana ($K \cdot \frac{N}{N+1}$ terlempar)** |
| **Distribusi Kunci (Uniformity)** | **Buruk**: Berpeluang terjadi hotspot ekstrem | **Sangat Baik**: Varians mendekati nol | Sangat Baik (Asumsi fungsi hash uniform) |
| **Dukungan Heterogenitas Mesin** | Sulit diimplementasikan | Mudah: Skalakan kuantitas vnodes per node | Tidak didukung secara alamiah |

### Pertimbangan Kritis:
1. **Pemilihan Fungsi Hash:** Jangan gunakan fungsi kriptografis lambat seperti SHA-512 atau bcrypt untuk layer *routing*. Gunakan algoritma *non-cryptographic* terdistribusi seragam seperti **MurmurHash3**, **xxHash**, atau **CityHash** yang mengeksekusi miliaran operasi per detik dengan overhead CPU rendah.
2. **Konkurensi Mutasi Ring:** Penambahan atau pengurangan simpul melibatkan mutasi struktur cincin. Diperlukan sinkronisasi thread-safe menggunakan *Read-Copy-Update (RCU)* atau *Read-Write Mutex (`sync.RWMutex`)* agar throughput pembacaan kunci (*lookup*) tidak terhambat selama *rebalancing*.

---

## SEKSI 11 — BEST PRACTICES

1. **Rasio Virtual Nodes Optimal:**
   Konfigurasikan $V$ antara **100 hingga 250 virtual nodes** per simpul fisik. Di bawah 50 vnodes, deviasi sebaran data terlalu lebar (hotspot). Di atas 300 vnodes, konsumsi memori cincin dan latensi pencarian biner meningkat tanpa memberikan signifikansi penurunan deviasi data.
2. **Kapasitas Terbobot (*Weighted Nodes*):**
   Jika node $A$ memiliki RAM 64GB dan node $B$ memiliki RAM 128GB, berikan node $B$ alokasi vnodes $2\times$ lebih banyak dibanding node $A$. Consistent hashing mengakomodasi rasio ini secara proporsional.
3. **Penyimpanan Lokal State Ring:**
   Klien (*Smart Clients*) atau API Gateway harus menyimpan salinan lokal cincin hash (*in-memory local cache*) untuk merutekan kueri langsung ke simpul yang benar tanpa *network hop* tambahan (*zero-hop routing*). Perubahan simpul disinkronisasi melalui protokol **Gossip** atau sistem koordinasi konsensus seperti Apache ZooKeeper / etcd.
4. **Replica Colocation Avoidance:**
   Dalam menentukan $R$ simpul replika, pastikan algoritma pemilihan tidak hanya memilih simpul fisik yang berbeda, tetapi juga memverifikasi bahwa simpul-simpul tersebut berada di **Rak (*Rack*) atau Zona Ketersediaan (*Availability Zone*) yang berbeda**.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Mengabaikan Virtual Nodes pada Implementasi Awal:**
   Banyak pengembang mengasumsikan cincin polos (*plain ring*) sudah cukup merata. Kenyataannya, distribusi acak $N$ titik pada lingkaran menghasilkan varians ukuran busur yang sangat masif, memicu satu node menampung beban hingga 400% di atas rata-rata.
2. **Hash Collisions pada Token Vnodes:**
   Membuat format nama vnode yang ambigu (misal: `node1` + `1` = `node11`, identik dengan `node11` + `""`). Gunakan delimiter tegas yang tidak mungkin muncul pada nama node (misal: `uuid-node:vnode-idx`).
3. **Menggunakan Struktur Data Linear Tanpa Binary Search:**
   Mengiterasi list cincin dari indeks 0 secara sekuensial ($O(M)$ di mana $M = N \times V$) alih-alih menggunakan binary search ($O(\log M)$). Pada cincin dengan 1.000 server dan 200 vnodes ($200.000$ entri), pencarian sekuensial menghancurkan *throughput* jaringan.
4. **Cascading Failure saat Node Mati Tanpa Grace Period:**
   Ketika sebuah node terputus sebentar akibat *garbage collection pause*, cincin langsung memutasi diri dan memicu migrasi data ratusan gigabyte. Gunakan mekanisme *heartbeat threshold* atau *circuit breaker* sebelum mengonfirmasi pelepasan node secara permanen.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Deteksi Persentase Migrasi Data (Beginner)
Tulis skrip Python untuk membuktikan kelemahan partisi modulo.
* **Tugas:** Simulasikan 10.000 data ID. Tentukan lokasi bucket-nya menggunakan modulo $N=10$. Naikkan simpul menjadi $N=11$. Hitung berapa persen data yang harus berpindah bucket. Bandingkan hasilnya dengan konsep Consistent Hashing.
* **Kriteria Keberhasilan:** Skrip menampilkan output empiris bahwa partisi modulo memindahkan $>80\%$ data saat $N$ berubah dari 10 ke 11.

### Latihan 2: Implementasi Weighted Consistent Hashing (Intermediate)
* **Tugas:** Modifikasi kelas `ProductionConsistentHashRing` dari Seksi 09 untuk mendukung parameter `weight: float` saat memanggil `add_node(node, weight=1.0)`.
* **Kriteria Keberhasilan:** Node dengan `weight=2.0` secara otomatis memegang alokasi vnodes dua kali lipat dibanding node dengan `weight=1.0`, dan diverifikasi melalui simulasi bahwa volume kunci yang diterima simpul tersebut terdistribusi $\approx 2:1$.

### Latihan 3: Rack-Aware Preference List Generator (Advanced)
* **Tugas:** Implementasikan fungsi replikasi data terdistribusi yang menerima metadata topologi fisik node berupa data `{"node_id": str, "rack_id": str}`. Buat fungsi pencarian `get_rack_aware_replicas(key, n_replicas)` yang menjamin bahwa tidak ada dua replika dari kunci yang sama ditempatkan pada `rack_id` yang identik.
* **Kriteria Keberhasilan:** Unit test membuktikan replikasi tersebar lintas rak berbeda meskipun token virtual node berurutan berada pada rak yang sama di dalam cincin.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. Jika sebuah klaster penyimpanan terdistribusi memiliki total $N$ simpul fisik dan $K$ total data kunci, berapa rata-rata volume kunci yang bermigrasi saat 1 simpul baru ditambahkan jika menggunakan Consistent Hashing?
   * A. $K$
   * B. $K / 2$
   * C. $K / (N + 1)$
   * D. $K \cdot (N / (N+1))$

2. Apa fungsi mendasar dari penambahan *Virtual Nodes* pada Consistent Hashing?
   * A. Mempercepat fungsi hash kriptografis.
   * B. Mengurangi varians sebaran data dan mencegah timbulnya *hotspot nodes*.
   * C. Mengamankan data dari ancaman serangan Man-In-The-Middle.
   * D. Mengurangi kompleksitas waktu pencarian kunci dari $O(\log M)$ menjadi $O(1)$.

3. Pada representasi cincin hash 32-bit, simpul $S_1$ berada pada token `1000`, dan simpul $S_2$ berada pada token `5000`. Di manakah sebuah kunci dengan hash `4200` akan disimpan secara konvensional (asumsi searah jarum jam)?
   * A. Simpul $S_1$
   * B. Simpul $S_2$
   * C. Terbagi 50:50 antara $S_1$ dan $S_2$
   * D. Tidak dapat disimpan (terjadi overflow cincin)

4. Mengapa algoritma seperti MurmurHash atau xxHash lebih dianjurkan untuk Consistent Hashing dibanding SHA-256 pada layer perutean router/klien?
   * A. SHA-256 tidak memiliki sifat keacakan bit yang seragam.
   * B. MurmurHash dan xxHash mengeksekusi operasi komputasi jauh lebih cepat dengan konsumsi CPU rendah karena tidak memerlukan properti keamanan kriptografis.
   * C. SHA-256 membatasi kapasitas maksimal cincin hingga 256 node saja.
   * D. MurmurHash secara otomatis menjamin ketiadaan tabrakan hash (*zero collision guaranteed*).

5. Algoritma pencarian paling optimal yang diterapkan pada array cincin token terurut berukuran $M$ (di mana $M = N \times V$) adalah:
   * A. Linear Search — $O(M)$
   * B. Binary Search — $O(\log M)$
   * C. Breadth-First Search — $O(V + E)$
   * D. Interpolation Search pada sembarang kondisi data — $O(\log(\log M))$

---

### Kunci Jawaban & Rasionalisasi
* **1. C :** Sesuai teorema Karger et al., penambahan node ke-$(N+1)$ hanya mengambil alih fraksi beban sebesar $1/(N+1)$ dari total data $K$, sehingga migrasi data bernilai $K/(N+1)$.
* **2. B :** Tanpa virtual nodes, sebaran simpul fisik di cincin bersifat acak diskrit dengan varians segmen sangat tinggi. Virtual nodes memecah cincin menjadi domain-domain kecil yang saling bersilangan untuk menjamin keseimbangan beban (*load balancing*).
* **3. B :** Dalam aturan searah jarum jam (*clockwise*), data dialokasikan ke token simpul pertama yang nilainya $\ge$ nilai hash data. Nilai $5000 \ge 4200$, sehingga kunci mendarat di $S_2$.
* **4. B :** Routing partisi adalah komputasi *in-path* berkecepatan tinggi. Kebutuhan utamanya adalah kecepatan dan uniformitas sebaran bit, bukan ketahanan terhadap serangan kriptanalisis (*collision resistance against malicious adversaries*).
* **5. B :** Token pada cincin hash disimpan dalam struktur data terurut, memungkinkan pencarian posisi target token via Binary Search dalam efisiensi asimptotik $O(\log M)$.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

### Makalah Akademis & Standar Industri
1. **Karger, D., Lehman, E., Leighton, T., Panigrahy, R., Levine, M., & Lewin, D. (1997).** *Consistent Hashing and Random Trees: Distributed Caching Protocols for Relieving Hot Spots on the World Wide Web.* ACM Symposium on Theory of Computing (STOC '97).
2. **DeCandia, G., Hastorun, D., Jampani, M., Kakulapati, G., Lakshman, A., Pilchin, A., Sivasubramanian, S., Vosshall, P., & Vogels, W. (2007).** *Dynamo: Amazon’s Highly Available Key-value Store.* ACM SIGOPS Operating Systems Review (SOSP '07).
3. **Lakshman, A., & Malik, P. (2010).** *Cassandra: A Decentralized Structured Storage System.* ACM SIGOPS Operating Systems Review.

### Buku Teks Fundamental
1. Kleppmann, Martin. (2017). *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems.* O'Reilly Media. (Chapter 6: Partitioning).
2. Tanenbaum, Andrew S., & Van Steen, Maarten. (2017). *Distributed Systems: Principles and Paradigms (3rd Edition).* CreateSpace Independent Publishing.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Partisi hashing modulo konvensional ($hash(k) \pmod N$) gagal melayani arsitektur terdistribusi elastis karena memicu migrasi data mendekati $100\%$ saat node bertambah atau berkurang.
2. **Consistent Hashing** menata ulang ruang hash ke dalam topologi cincin kontinu, membatasi perpindahan data hanya pada batas teoritis $K/N$ saat terjadi perubahan keanggotaan simpul (*membership change*).
3. Penerapan **Virtual Nodes (Vnodes)** memetakan setiap simpul fisik ke ratusan posisi semu di cincin hash. Teknik ini mengeliminasi masalah segmentasi busur timpang (*data skewness*) dan menurunkan koefisien variasi distribusi data hingga di bawah $5\%$.
4. Pencarian pemilik kunci di dalam cincin terurut dieksekusi menggunakan **Binary Search** dengan kompleksitas $O(\log(N \cdot V))$, menjadikannya mekanisme perutean data yang sangat cepat dan terukur secara matematis.

---

## SEKSI 17 — GLOSARIUM

* **Consistent Hashing:** Teknik pemetaan data ke simpul di mana penambahan atau pengurangan simpul hanya memindahkan kunci milik tetangganya langsung tanpa merombak pemetaan global.
* **Hash Ring:** Struktur lingkaran konseptual yang merepresentasikan seluruh domain keluaran dari fungsi hash (misal: rentang integer tak bertanda dari 0 hingga $2^{32}-1$).
* **Virtual Node (Vnode):** Titik representasi logis dari suatu simpul fisik pada cincin hash untuk mendistribusikan beban secara homogen.
* **Cache Stampede:** Kondisi masifnya kueri yang membobol lapisan cache secara simultan akibat data cache hilang/berpindah serempak, melumpuhkan database utama.
* **Preference List:** Urutan simpul fisik unik yang bertanggung jawab menampung replika salinan dari suatu kunci tertentu dalam sistem basis data terdistribusi.
* **Skewness:** Ketidakseimbangan distribusi data di mana satu atau beberapa simpul menampung porsi volume data yang jauh melampaui kapasitas simpul lainnya.
* **Clockwise Lookup:** Mekanisme penentuan alokasi simpul dengan menelusuri cincin dari posisi hash kunci menuju nilai token simpul pertama yang lebih besar atau sama dengannya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Pacing & Alokasi Waktu Pembelajaran
* **Teori & Masalah Modulo (45 Menit):** Tekankan kegagalan partisi modulo. Minta peserta menghitung secara manual perpindahan data dari $N=3$ ke $N=4$ agar urgensi masalah terlihat konkret.
* **Mekanisme Cincin & Binary Search (60 Menit):** Bongkar implementasi `bisect_right` / binary search. Tunjukkan edge case saat hash kunci melampaui token node terbesar (masalah *wrapping around* cincin kembali ke index 0).
* **Hands-On Virtual Nodes (75 Menit):** Ajak siswa memvisualisasikan data skewness tanpa vnodes vs dengan 200 vnodes menggunakan simulasi script Seksi 09. Tunjukkan bagaimana standar deviasi menyusut tajam.
* **Lab Arsitektur Lanjutan (60 Menit):** Bedah penerapan teknik ini pada arsitektur nyata: Amazon DynamoDB dan Apache Cassandra.

### Tip Pedagogi
* Jangan gunakan fungsi hash kriptografis bawaan Python (`hash()`) untuk mendemonstrasikan algoritma ini kepada peserta karena Python menambahkan *hash randomization seed* secara default saat proses restart, yang menyebabkan nilai hash berubah antar-eksekusi program. Gunakan pustaka eksplisit seperti `hashlib.sha256` atau `mmh3`.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** `1.0.0` (Rilis Kurikulum Inti)
* **Tanggal:** 27 Maret 2026
* **Perubahan Terakhir:** 
  * Peluncuran draf komprehensif Bab 10 Modul 01.
  * Standarisasi implementasi Production-Grade Ring menggunakan MurmurHash3 dan Binary Search.
  * Penambahan diagram alur transisi data dan simulasi deviasi standar.
* **Author/Reviewer:** Senior Technical Curriculum Architect (Core Foundations Track).

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `DSA-01-CF-09-04` — *String Matching: Boyer-Moore & KMP (Knuth-Morris-Pratt)*
* **Modul Saat Ini:** `DSA-01-CF-10-01` — *Consistent Hashing & Virtual Nodes (Hashing Konsisten & Partisi Terdistribusi)*
* **Modul Selanjutnya:** `DSA-01-CF-10-02` — *Vector Clocks, Version Vectors & Distributed Causal Consistency*