# Kurikulum Enterprise Rekayasa Perangkat Lunak: Python Internals & Architecture
## Bab 03: Struktur Data Lanjutan & Memory Management
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Membedah CPython Memory Architecture**: Memahami anatomi alokasi memori internal CPython, mulai dari hierarki Arena, Pool, dan Block pada PyMalloc hingga struktur biner objek C (`PyObject`, `PyVarObject`, dan `PyGC_Head`).
2. **Menguasai Mekanisme Dual-Engine Garbage Collection**: Mendiagnosis siklus hidup memori melalui kombinasi deterministik *Reference Counting* dan heuristik *Generational Garbage Collection* (Gen 0, Gen 1, Gen 2) untuk mengeliminasi *cyclic references*.
3. **Mengimplementasikan Pola Zero-Copy Data Processing**: Memanfaatkan PEP 3118 Buffer Protocol, `memoryview`, dan `bytearray` untuk meniadakan overhead duplikasi *byte buffer* pada pipeline I/O throughput tinggi.
4. **Mereduksi Memory Footprint Skala Enterprise**: Menerapkan optimasi struktur data via `__slots__`, *interning*, dan *Flyweight pattern* guna menurunkan *heap consumption* hingga >60% pada arsitektur berbasis mikrosServis.
5. **Mendiagnosis dan Menanggulangi Memory Leak di Lingkungan Produksi**: Menggunakan instrumentasi diagnosa tingkat rendah (`tracemalloc`, `gc`, `objgraph`, dan `sys.getsizeof` traversal) untuk memitigasi fragmentasi memori dan lonjakan latensi (*Stop-the-World pauses*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Fundamental bahasa pemrograman Python (OOP lanjutan, dunder methods, *decorators*, generator).
* Konsep arsitektur komputer: Stack vs. Heap memory, alokasi pointer C/C++, struktur *cache locality* CPU (L1/L2/L3), dan *virtual memory paging*.
* Pemahaman dasar tentang algoritma dan kompleksitas waktu/ruang (Big-O notation).
* Pengalaman mengoperasikan CLI Linux, Git, dan menjalankan modul diagnosa dasar Python.

---

### 3. Concept & Internal Architecture (Mendalam)

Python mengabstraksi manajemen memori dari pengembang, namun abstraksi ini memiliki biaya komputasi yang signifikan jika arsitektur internal CPython tidak dipahami secara mendalam.

```
+-----------------------------------------------------------------------+
|                           Aplikasi Python                             |
+-----------------------------------------------------------------------+
|  Objek Python: int, list, dict, custom classes, dll.                  |
+-----------------------------------------------------------------------+
|                           PyMalloc Engine                             |
|  (Alokator Khusus CPython untuk Alokasi Kecil: <= 512 bytes)          |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | Arenas (256 KB aligned pada Virtual Memory)                     |  |
|  |  +-----------------------------------------------------------+  |  |
|  |  | Pools (4 KB = 1 Memory Page OS)                           |  |  |
|  |  |  +-----------------------------------------------------+  |  |  |
|  |  |  | Blocks (Ukuran seragam per Pool: 8, 16, ..., 512 B) |  |  |  |
|  |  |  +-----------------------------------------------------+  |  |  |
|  |  +-----------------------------------------------------------+  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
|                       System Malloc (glibc / OS)                      |
|  (Alokasi Objek Besar: > 512 bytes dialokasikan via malloc/free)      |
+-----------------------------------------------------------------------+
|                         Sistem Operasi / Kernel                       |
|  (Virtual Memory Management, Paging, MMU)                             |
+-----------------------------------------------------------------------+
```

#### 3.1. Anatomi Alokasi Memori: PyMalloc vs. System Malloc
CPython membagi strategi alokasi memorinya ke dalam dua jalur utama berdasarkan ukuran *payload*:

1. **Small Object Allocator (PyMalloc)**:
   * Menangani alokasi berukuran $\le 512$ bytes.
   * **Arenas (256 KB)**: Ruang memori berkelanjutan yang dialokasikan langsung dari OS melalui `malloc()`. Arena mempertahankan status alokasi pool yang terisi (*used*), kosong (*empty*), atau penuh (*full*).
   * **Pools (4 KB)**: Sub-divisi dari arena yang berukuran setara dengan satu *page* sistem operasi. Setiap pool hanya menangani alokasi *block* dengan *size class* tetap (tersedia dalam kelipatan 8 bytes: 8, 16, 24, ..., 512 bytes).
   * **Blocks**: Unit atomik di dalam pool tempat objek dialokasikan. Alokasi dan dealokasi block dikelola via *singly-linked free-list* internal tanpa fragmentasi eksternal di dalam pool.
2. **System Malloc**:
   * Setiap alokasi objek $> 512$ bytes langsung dialihkan ke alokator bawaan sistem operasi (misalnya, `ptmalloc` glibc atau `jemalloc`). PyMalloc di-bypass untuk mencegah fragmentasi berlebih pada memory arena.

#### 3.2. Struktur Internal PyObject dan PyVarObject
Setiap entitas di Python adalah pointer ke sebuah C *struct*. Objek paling primitif tidak pernah hanya memuat nilai datanya saja:

```c
// Definisi konseptual dari cpython/Include/object.h
typedef struct _object {
    _PyObject_HEAD_EXTRA // Pointer untuk tracking doubly-linked list alokator
    Py_ssize_t ob_refcnt; // Reference counter (8 bytes pada sistem 64-bit)
    struct _typeobject *ob_type; // Pointer ke tipe data objek (8 bytes)
} PyObject;

typedef struct {
    PyObject ob_base;
    Py_ssize_t ob_size; // Menyimpan jumlah elemen (8 bytes) untuk container dinamis
} PyVarObject;
```

* **Overhead Dasar**: Sebuah integer kosong atau bernilai kecil di Python 64-bit membutuhkan minimum 28 bytes: 8 bytes untuk `ob_refcnt`, 8 bytes untuk pointer `ob_type`, dan sisanya untuk representasi nilai digit serta padding C.
* **Overhead PyGC_Head**: Objek gabungan/kontainer (*containers*) yang dapat menyebabkan referensi melingkar (*lists*, *dicts*, *tuples*, *custom classes*) memiliki header tambahan berupa `PyGC_Head` (16 bytes) sebelum struktur `PyObject`. Header ini digunakan oleh Generational GC untuk menyusun pelacakan graf referensi.

#### 3.3. Dual-Engine Garbage Collection: Reference Counting & Generational GC
CPython mengombinasikan dua arsitektur untuk membersihkan memori yang tidak lagi terpakai:

1. **Reference Counting Engine**:
   * Setiap kali objek direferensikan (variabel baru, dimasukkan ke list, argumen fungsi), nilai `ob_refcnt` dinaikkan secara atomik/inkremental.
   * Saat referensi keluar dari *scope* atau dihapus (`del`), `ob_refcnt` diturunkan.
   * Jika `ob_refcnt == 0`, CPython langsung mengembalikan blok memori tersebut ke pool PyMalloc secara deterministik tanpa *latency delay*.
   * **Kelemahan**: Tidak mampu mendeteksi *cyclic references* (Objek A mereferensikan Objek B, dan Objek B mereferensikan Objek A, sementara keduanya terisolasi dari variabel *root* program).

2. **Generational Garbage Collection Engine**:
   * Mengatasi masalah referensi melingkar dengan mendeteksi *unreachable cycles*.
   * Objek kontainer dikelompokkan ke dalam 3 generasi berdasarkan usia kelangsungan hidupnya:
     * **Generation 0 (Gen 0)**: Menampung objek-objek yang baru dialokasikan. Alokasi dipindai secara sangat reguler.
     * **Generation 1 (Gen 1)**: Menampung objek yang selamat dari siklus pemindaian Gen 0.
     * **Generation 2 (Gen 2)**: Objek dengan masa hidup panjang (*long-lived*), seperti konfigurasi aplikasi atau *singleton cache*.
   * **Algoritma Cyclic GC**:
     1. Menetapkan nilai `gc_refs` pada setiap objek dalam generasi yang sedang diperiksa, disalin dari nilai aktual `ob_refcnt`.
     2. Melakukan iterasi internal pada setiap kontainer dan menurunkan nilai `gc_refs` dari objek-objek anak yang direferensikannya.
     3. Objek yang memiliki `gc_refs == 0` setelah traversal diisolasi ke dalam kelompok kandidat *unreachable*.
     4. Objek yang terbukti tidak dapat dijangkau dari *root reference* akan dideallokasikan; sisanya dipromosikan ke generasi berikutnya.

#### 3.4. Buffer Protocol & Zero-Copy Architecture
Data slicing konvensional pada tipe `bytes` (`data[0:1024]`) menghasilkan alokasi memori baru di heap dan menyalin urutan byte tersebut secara penuh ($O(N)$ memory duplication).

PEP 3118 mendefinisikan *Buffer Protocol* di level C, yang memungkinkan suatu objek Python mengekspos pointer internal ke memori raw-nya. Objek `memoryview` membungkus pointer ini dan memungkinkan manipulasi irisan (*slicing*), pengindeksan, serta mutasi in-place secara $O(1)$ tanpa membuat alokasi duplikat pada memori heap (*Zero-Copy*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional Python | Pendekatan Arsitektur Produksi Lanjutan |
| :--- | :--- | :--- |
| **Representasi State Objek** | Berbasis instance `__dict__` dinamis bawaan kelas. | Berbasis `__slots__` statis atau `struct.Struct` binary packing. |
| **Konsumsi Heap per Instansi** | ~152 bytes hingga ratusan bytes per instansi kosong karena alokasi dictionary. | 48 hingga 56 bytes per instansi (tanpa alokasi `__dict__` overhead). |
| **Manipulasi I/O Binary** | Menggunakan slicing `bytes` reguler ($O(N)$ copy per sub-array). | Menggunakan `memoryview` dan buffer protocol ($O(1)$ pointer shift). |
| **Mitigasi Reference Cycle** | Bergantung sepenuhnya pada siklus GC otomatis bawaan. | Memutus siklus via `weakref`, pooling, atau isolasi GC pada *hot-path*. |
| **Perilaku Garbage Collection** | Pemicuan Gen 2 GC non-deterministik memicu *STW (Stop-the-World) pauses*. | Penyetelan `gc.set_threshold()`, GC manual scheduling, atau `gc.freeze()`. |

**Mengapa ini krusial di Produksi?**
Pada aplikasi terdistribusi, *streaming broker*, atau *low-latency engine* yang memproses puluhan ribu transaksi per detik, penumpukan objek berukuran kecil menghasilkan fragmentasi PyMalloc Arena. Kondisi ini memicu pemanggilan Generational GC Gen 2 secara terus-menerus. Selama GC Gen 2 berjalan, CPython menghentikan eksekusi kode utama (*Stop-the-World pause*), yang dapat meningkatkan latensi P99 dari <5ms menjadi >250ms secara mendadak.

---

### 5. How (Workflow detail)

Berikut adalah tahapan sistematis alokasi dan penanganan memori di level CPython:

```
[Inisiasi Pembuatan Objek di Kode Python]
                   |
                   v
        Apakah ukuran <= 512 bytes?
        /                         \
      (Ya)                       (Tidak)
      /                             \
     v                               v
[PyMalloc Allocator]         [OS System Malloc]
     |                               |
     +--> Cari Pool yang sesuai      +--> Alokasi via libc malloc
     |    (Size Class 8-512)         |
     +--> Ambil Block dari Free-list |
                   |                 |
                   +--------+--------+
                            |
                            v
       [Inisialisasi ob_refcnt = 1, pasang ob_type]
                            |
           Apakah Objek bertipe Container?
                   /                 \
                 (Ya)               (Tidak)
                 /                     \
                v                       v
      [Sematkan PyGC_Head]      [Hanya Objek Polos]
      [Daftarkan ke Gen 0]              |
                \                       /
                 +----------+----------+
                            |
                            v
                 [Objek Beroperasi Aktif]
                            |
             (Referensi Objek Dihapus / Keluar Scope)
                            |
                            v
                    [ob_refcnt -= 1]
                            |
                    Apakah ob_refcnt == 0?
                    /                    \
                  (Ya)                  (Tidak)
                  /                        \
                 v                          v
      [Deallokasi Instan]       [Apakah Terjebak Cyclic?]
      [Kembalikan Block ke Pool]            |
                                    (Ya, siklus terisolasi)
                                            |
                                            v
                                  [Terdeteksi oleh GC Gen]
                                  [Pemutusan Siklus & Deallokasi]
```

1. **Jalur Alokasi**: CPython mengevaluasi ukuran payload. Objek kecil dipetakan ke pool PyMalloc yang telah dialokasikan sebelumnya di virtual memory. Objek kontainer mendapatkan wrapper `PyGC_Head` dan ditautkan ke *doubly-linked list* Gen 0.
2. **Jalur Evaluasi Gen 0 Sweep**: Setiap alokasi baru menaikkan penghitung alokasi Gen 0. Ketika selisih alokasi melampaui ambang batas (`threshold 0`), siklus GC Gen 0 dieksekusi hanya untuk memeriksa objek-objek baru.
3. **Jalur Promosi Generasi**: Objek yang lolos dari eliminasi siklus Gen 0 dipromosikan ke tautan Gen 1. Begitu pula objek Gen 1 yang bertahan dipromosikan ke Gen 2.
4. **Jalur Zero-Copy Processing**: Saat data diterima melalui socket atau file stream ke dalam `bytearray`, objek `memoryview` dipetakan ke pointer memori yang ada. Slicing memori hanya mengubah *offset* pointer dan panjang ukuran (*length*) pada deskriptor C buffer tanpa merealokasi heap.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Kota vs. Sewa Loker Mandiri
* **Default CPython (`dict`)**: Mirip menyewa rumah berukuran besar hanya untuk meletakkan sebuah buku. Di dalam rumah tersebut, Anda harus membayar biaya ruang tamu, dapur, dan lorong (`__dict__` overhead dan dynamic resizing hash table) meskipun barang bawaan Anda hanya satu baris data.
* **Optimasi `__slots__`**: Mirip memesan loker khusus di stasiun yang dirancang persis sesuai ukuran barang. Anda hanya membayar ruang yang digunakan secara presisi tanpa ada ruang ekstra untuk barang tak dikenal.
* **Memoryview (Zero-Copy)**: Mirip membaca buku langsung di etalase toko buku melalui kaca pembesar pada bab yang diinginkan, bukan membeli buku baru lalu memfotokopi bab tersebut ke kertas lain hanya untuk dibaca di meja kasir.

```
DIAGRAM: ALOKASI MEMORI PYMALLOC (ARENA -> POOL -> BLOCK)

[ ARENA 256 KB ] (Dialokasikan dari OS)
+-----------------------------------------------------------------------+
| POOL 0 (4 KB)       | POOL 1 (4 KB)       | POOL N (4 KB)             |
| [Class 16 Bytes]    | [Class 64 Bytes]    | [Class 512 Bytes]         |
| +-----------------+ | +-----------------+ | +-----------------------+ |
| | Block 0 (16 B)  | | | Block 0 (64 B)  | | | Block 0 (512 B)       | |
| | Block 1 (16 B)  | | | Block 1 (64 B)  | | | Block 1 (512 B)       | |
| | [Free-list ...] | | | [Free-list ...] | | | [Free-list ...]       | |
| +-----------------+ | +-----------------+ | +-----------------------+ |
+-----------------------------------------------------------------------+

DIAGRAM: STANDARD SLICING VS ZERO-COPY MEMORYVIEW

Standard Slicing: data[2:6]
Source Buffer: [ 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' ]
                             |     |     |     |
                             v     v     v     v
Heap Realokasi:            [ 'C' | 'D' | 'E' | 'F' ]  <-- Duplikasi Data Baru (O(N))

Zero-Copy Memoryview: memoryview(data)[2:6]
Source Buffer: [ 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' ]
                             ^                 ^
                             |                 |
memoryview pointer: ---------[ offset=2, len=4 ]      <-- Hanya Pointer Metadata (O(1))
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Perbandingan Memory Footprint `__dict__` vs `__slots__` dan Reference Tracking

```python
import sys
import gc

class StandardSession:
    def __init__(self, session_id: str, user_id: int):
        self.session_id = session_id
        self.user_id = user_id

class OptimizedSession:
    __slots__ = ('session_id', 'user_id')
    def __init__(self, session_id: str, user_id: int):
        self.session_id = session_id
        self.user_id = user_id

def inspect_memory_and_references():
    s_std = StandardSession("sess_abc123", 1001)
    s_opt = OptimizedSession("sess_abc123", 1001)

    # 1. Analisis Ukuran Instansi Dasar
    # sys.getsizeof() hanya menghitung overhead shallow objek dasar
    print(f"Shallow size StandardSession: {sys.getsizeof(s_std)} bytes")
    print(f"Shallow size OptimizedSession: {sys.getsizeof(s_opt)} bytes")

    # Objek standard memiliki __dict__ tambahan yang memakan alokasi heap besar
    dict_overhead = sys.getsizeof(s_std.__dict__)
    print(f"Overhead __dict__ pada StandardSession: {dict_overhead} bytes")
    print(f"Total kalkulasi Standard: {sys.getsizeof(s_std) + dict_overhead} bytes")

    # 2. Tracking Reference Counting
    target_data = ["payload_node"]
    print(f"\nRef count awal target_data: {sys.getrefcount(target_data) - 1}") # Dikurangi 1 untuk getrefcount temp ref

    alias_ref = target_data
    print(f"Ref count setelah di-alias: {sys.getrefcount(target_data) - 1}")

    del alias_ref
    print(f"Ref count setelah alias dihapus: {sys.getrefcount(target_data) - 1}")

if __name__ == "__main__":
    inspect_memory_and_references()
```

#### 7.2. Practical Example: Zero-Copy Network Binary Protocol Unpacker
Implementasi parser paket jaringan biner (misal: header paket 8-byte, payload dinamis) menggunakan `memoryview` untuk memastikan tidak ada alokasi buffer string berulang saat membaca stream data besar.

```python
import struct
from typing import Generator, Tuple

# Format Header Paket:
# Magic Byte (2B) = 'PK' (0x50, 0x4B)
# Payload Size (2B) = Unsigned Short (H)
# Sequence ID (4B) = Unsigned Int (I)
HEADER_FORMAT = "!2sHI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

class ZeroCopyPacketParser:
    """
    Parser paket biner berbasis Zero-Copy memanfaatkan Python Buffer Protocol.
    Menghindari alokasi string baru saat mengiris (slicing) stream byte mentah.
    """
    def __init__(self, stream_buffer: bytearray):
        # Membungkus buffer utama dengan memoryview (Zero-Copy)
        self._view = memoryview(stream_buffer)
        self._length = len(stream_buffer)

    def parse_packets(self) -> Generator[Tuple[int, memoryview], None, None]:
        offset = 0

        while offset + HEADER_SIZE <= self._length:
            # Mengiris header tanpa alokasi memori baru di heap
            header_slice = self._view[offset : offset + HEADER_SIZE]
            magic, payload_len, seq_id = struct.unpack(HEADER_FORMAT, header_slice)

            if magic != b'PK':
                raise ValueError(f"Protokol korup pada offset {offset}: Magic Byte tidak valid")

            packet_start = offset + HEADER_SIZE
            packet_end = packet_start + payload_len

            if packet_end > self._length:
                # Buffer belum lengkap, menunggu transfer chunk berikutnya
                break

            # Ekstraksi payload murni menggunakan sub-memoryview
            payload_view = self._view[packet_start:packet_end]
            yield seq_id, payload_view

            # Menggeser pointer pembacaan secara linear
            offset = packet_end

def simulate_pipeline():
    # Simulasi stream data biner mentah masuk dari socket OS ke bytearray
    raw_stream = bytearray()
    
    # Buat 3 paket tiruan
    for seq in range(1, 4):
        body = f"MESSAGE_BODY_DATA_{seq}".encode('utf-8')
        header = struct.pack(HEADER_FORMAT, b'PK', len(body), seq)
        raw_stream.extend(header)
        raw_stream.extend(body)

    # Inisialisasi parser performa tinggi
    parser = ZeroCopyPacketParser(raw_stream)
    
    for seq_id, payload in parser.parse_packets():
        # Membaca isi payload tanpa menyalin buffer memori
        # .tobytes() hanya dipanggil ketika mutlak perlu deserialisasi ke domain level tinggi
        print(f"[Engine] Parsed Packet ID: {seq_id} | Size: {len(payload)}B | Data: {payload.tobytes().decode('utf-8')}")

if __name__ == "__main__":
    simulate_pipeline()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform *High-Frequency Telemetry Ingestion* untuk industri logistik IoT memproses **80.000 events/detik** menggunakan cluster FastAPI/AsyncIO di AWS ECS. 
Setiap node menerima JSON telemetry, memvalidasinya ke dalam instance model, melakukan transformasi, dan meneruskannya ke Kafka broker.

#### Gejala di Lingkungan Produksi
1. Rata-rata CPU stabil di 45%, namun setiap 40-60 detik terjadi **lonjakan latensi drastis (P99 spike dari 6ms melonjak menjadi 320ms)**.
2. Munculnya ancaman *connection drops* dan *timeout cascading* pada upstream API Gateway.
3. Analisis Linux memory cgroup menunjukkan lonjakan memori progresif (*memory ramp-up*) hingga memicu *OOMKilled* (Out-Of-Memory Killer) setiap 6 jam operasi.

#### Investigasi Akar Masalah (Root Cause Analysis)
1. Tim melakukan profiling latensi dengan mengaitkan `gc.callbacks`. Ditemukan bahwa lonjakan latensi berkorelasi langsung dengan siklus pembersihan **Generational GC Generation 2**.
2. Jutaan objek dictionary dinamis kecil yang dibuat per request masuk ke Gen 0, dan karena tingginya volume pemanggilan asinkron, sebagian objek selamat dari Gen 0/Gen 1 lalu terdorong ke Gen 2.
3. Pemindaian Gen 2 memerlukan penelusuran jutaan pointer kontainer di memori secara komprehensif, memicu *Stop-the-World pause* selama ratusan milidetik.
4. Selain itu, ditemukan *cyclic reference* yang tidak disengaja pada *middleware error-tracking*: exception objek menyimpan frame traceback, yang mereferensikan variabel lokal fungsi, yang pada akhirnya memegang kembali instansi handler.

#### Solusi Arsitektural

```
[Arsitektur Sebelum Optimasi]
Client --> FastAPI JSON Payload --> Instansi Model Standar (__dict__) 
       --> Cyclic Handler Ref --> GC Gen 2 Terakumulasi --> STW Freeze (320ms)

[Arsitektur Setelah Optimasi]
Client --> Binary/Compact Stream --> __slots__ Dataclasses & Buffer Reuse 
       --> Explicit Traceback Cleanup 
       --> Tuning GC: gc.disable() pada Hot-Path + Manual GC Batching --> Latensi P99 < 8ms
```

1. **Konversi Domain Model ke `__slots__`**: Seluruh representasi data transfer diubah menjadi kelas berbasis `__slots__` statis. Pengurangan ukuran objek menghemat memori sebesar ~62%.
2. **Pembersihan Siklus Traceback**: Pada blok *exception handler*, implementasikan eliminasi eksplisit referensi frame:
   ```python
   except Exception as err:
       try:
           handle_error(err)
       finally:
           del err  # Memutus siklus referensi trace frame CPython
   ```
3. **GC Throttling & Offloading Engine**:
   Alih-alih membiarkan CPython melakukan GC Gen 2 otomatis selama puncak beban, sistem menerapkan kontrol deterministik:
   ```python
   # Diinisialisasi saat bootstrap worker
   import gc
   
   # Naikkan ambang batas alokasi agar GC Gen 2 tidak terpicu sembarangan
   # Default CPython biasanya (700, 10, 10)
   gc.set_threshold(50000, 20, 20)
   ```
4. **Hasil**: Latensi P99 turun permanen ke 7.2ms. Penggunaan memori berkurang dari 1.8 GB per worker menjadi 480 MB konstan tanpa kebocoran memori (OOM eliminated).

---

### 9. Trade-offs

| Pendekatan | Keuntungan (*Pros*) | Kerugian / Biaya (*Cons*) |
| :--- | :--- | :--- |
| **`__slots__` Classes** | - Menghilangkan overhead `__dict__`.<br>- Akses atribut lebih cepat via C-level offset.<br>- Mencegah *typo* atribut runtime. | - Fleksibilitas dynamic patching hilang.<br>- Pewarisan (*inheritance*) menjadi lebih rumit jika kelas induk tidak mendefinisikan `__slots__`. |
| **Zero-Copy (`memoryview`)** | - Meniadakan duplikasi buffer memori.<br>- Kompleksitas waktu slicing adalah $O(1)$.<br>- Sangat hemat alokasi OS heap. | - Objek yang dibungkus tidak dapat di-resize ukurannya selama view aktif.<br>- Kode menjadi lebih *verbose* dan rentan *type error* jika salah menangani decoding. |
| **Manual GC Tuning (`gc.disable` / Thresholding)** | - Menghilangkan *Stop-the-World pauses* tak terduga pada *hot-path* transaksi.<br>- Latensi aplikasi sangat terprediksi. | - Jika terjadi *cyclic reference* yang bocor, memori akan naik tak terbatas hingga OOM jika manual sweep tidak diatur dengan cermat. |
| **Weak References (`weakref`)** | - Mencegah siklus referensi yang menahan objek di memori.<br>- Ideal untuk cache metadata internal. | - Akses nilai memerlukan validasi `None` (karena objek bisa mati sewaktu-waktu).<br>- Tipe bawaan tertentu (`list`, `int`) tidak mendukung `weakref` langsung. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Memory Leak Terselubung via Closure / Default Mutable Argument
* **Anti-Pattern**: Menggunakan objek yang dapat bermutasi sebagai *default parameter* atau mengikat konteks besar ke dalam *long-lived closure*.
  ```python
  # KESALAHAN: cache default argument hidup selama runtime modul bertahan
  def process_transaction(tx_id: str, context_cache: dict = {}):
      context_cache[tx_id] = retrieve_payload(tx_id)
      return evaluate(context_cache)
  ```
* **Remediasi**: Selalu gunakan `None` sebagai sentinel value dan inisialisasi lokal:
  ```python
  def process_transaction(tx_id: str, context_cache: dict | None = None):
      if context_cache is None:
          context_cache = {}
      context_cache[tx_id] = retrieve_payload(tx_id)
      return evaluate(context_cache)
  ```

#### Kesalahan 2: Menggunakan `sys.getsizeof()` Tanpa Traversal Rekursif
* **Anti-Pattern**: Berasumsi `sys.getsizeof([dict(), dict()])` mencerminkan penggunaan memori riil seluruh struktur kontainer.
* **Fakta**: `sys.getsizeof` hanya mengukur array pointer dari list tersebut (ukuran shallow), bukan objek yang dirujuknya.
* **Remediasi**: Gunakan modul `tracemalloc` untuk pengukuran alokasi memori aktual per file/baris program.

#### Kesalahan 3: Slicing Bytes Secara Naif di Dalam Perulangan Stream
* **Anti-Pattern**: Mengonsumsi stream soket besar dengan `chunk = stream_bytes[start:end]` di dalam loop jutaan iterasi, yang memicu lonjakan alokasi transien pada PyMalloc.
* **Remediasi**: Bungkus seluruh buffer dengan `memoryview(stream_bytes)` sebelum perulangan slicing.

#### Langkah Diagnosa (Troubleshooting Checklist)
1. **Verifikasi Alokasi Memori dengan `tracemalloc`**:
   ```python
   import tracemalloc
   tracemalloc.start()
   # Eksekusi fungsi tersangka
   snapshot = tracemalloc.take_snapshot()
   top_stats = snapshot.statistics('lineno')
   for stat in top_stats[:5]:
       print(stat)
   ```
2. **Identifikasi Objek Tanpa Deallokasi Menggunakan `gc`**:
   ```python
   import gc
   gc.collect()
   print("Objek tak terjangkau:", gc.garbage)
   ```
3. **Deteksi Cyclic Reference Langsung**:
   Gunakan pustaka pihak ketiga seperti `objgraph` untuk merender graf SVG visual rantai referensi yang menahan objek di Gen 2.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `__slots__` pada Semua DTO/Entity Kelas Tinggi**: Pastikan setiap kelas domain model yang diinstansiasi lebih dari 10.000 kali menggunakan tuple `__slots__`.
- [ ] **Terapkan `memoryview` untuk I/O Biner**: Jangan pernah mengiris (`slicing`) tipe `bytes` berukuran $> 64$ KB secara berulang tanpa `memoryview`.
- [ ] **Putus Referensi Exception Explicitly**: Tambahkan blok `finally: del err` pada alur tangkapan error yang memproses transaksi krusial.
- [ ] **Kalibrasi Ulang Ambang Batas GC**: Pada service asinkron (*FastAPI*, *Tornado*, *Sanic*), kalibrasikan ambang batas GC dengan `gc.set_threshold()` sesuai metrik beban throughput riil.
- [ ] **Hindari Penggunaan `__del__` Finalizer**: Jangan mendeklarasikan metode `__del__` pada kelas yang rentan mengalami referensi siklik; gunakan context manager (`with` statement) untuk manajemen lifecycle resource.
- [ ] **Pantau Fragmentasi Arena**: Periksa statistik internal memory allocator secara periodik menggunakan `sys._debugmallocstats()` di tahap staging untuk mengamati utilisasi pool PyMalloc.

---

### 12. Hands-on Practice

Buat dan susun direktori praktikum berikut di mesin Anda:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

#### Langkah 1: Script Monitoring Alokasi Memori Real-Time (`memory_profiler.py`)
Simpan kode berikut sebagai `hands-on/m02/memory_profiler.py`:

```python
# hands-on/m02/memory_profiler.py
import tracemalloc
import sys
import time

class NormalPayload:
    def __init__(self, trace_id: int, payload: str):
        self.trace_id = trace_id
        self.payload = payload

class SlottedPayload:
    __slots__ = ('trace_id', 'payload')
    def __init__(self, trace_id: int, payload: str):
        self.trace_id = trace_id
        self.payload = payload

def benchmark_instantiation(cls, iterations: int):
    tracemalloc.start()
    start_time = time.perf_counter()
    
    # Alokasi koleksi objek besar
    storage = [cls(i, "DATA_PACKET_CONTENT_PAYLOAD") for i in range(iterations)]
    
    elapsed = time.perf_counter() - start_time
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"[{cls.__name__}]")
    print(f"  Execution Time: {elapsed:.4f} detik")
    print(f"  Current Memory: {current / 1024 / 1024:.2f} MB")
    print(f"  Peak Memory   : {peak / 1024 / 1024:.2f} MB")
    return storage

if __name__ == "__main__":
    ITERATIONS = 500_000
    print(f"Menjalankan benchmark alokasi untuk {ITERATIONS} instansi...")
    
    ref1 = benchmark_instantiation(NormalPayload, ITERATIONS)
    del ref1 # Paksa pelepasan memori
    
    ref2 = benchmark_instantiation(SlottedPayload, ITERATIONS)
    del ref2
```

#### Langkah 2: Script Zero-Copy Buffer Processing (`zero_copy_engine.py`)
Simpan kode berikut sebagai `hands-on/m02/zero_copy_engine.py`:

```python
# hands-on/m02/zero_copy_engine.py
import time
import os

def generate_dummy_binary_file(filename: str, size_mb: int):
    # Buat file biner dummy
    with open(filename, "wb") as f:
        f.write(os.urandom(size_mb * 1024 * 1024))

def slice_with_copy(data: bytes, chunk_size: int):
    total = len(data)
    idx = 0
    checksum = 0
    start = time.perf_counter()
    while idx < total:
        chunk = data[idx : idx + chunk_size] # Realokasi memori heap baru
        checksum += chunk[0]
        idx += chunk_size
    elapsed = time.perf_counter() - start
    print(f"Standard Bytes Slicing: {elapsed:.4f} detik (Checksum: {checksum})")

def slice_zero_copy(data: bytes, chunk_size: int):
    view = memoryview(data)
    total = len(data)
    idx = 0
    checksum = 0
    start = time.perf_counter()
    while idx < total:
        chunk = view[idx : idx + chunk_size] # Pointer shift, Zero heap realokasi
        checksum += chunk[0]
        idx += chunk_size
    elapsed = time.perf_counter() - start
    print(f"Zero-Copy Memoryview Slicing: {elapsed:.4f} detik (Checksum: {checksum})")

if __name__ == "__main__":
    FILE_NAME = "buffer_source.bin"
    SIZE_MB = 120
    CHUNK_SIZE = 1024 # 1 KB chunk
    
    print(f"Menyiapkan {SIZE_MB}MB binary file...")
    generate_dummy_binary_file(FILE_NAME, SIZE_MB)
    
    with open(FILE_NAME, "rb") as f:
        raw_bytes = f.read()

    print("Memulai komparasi slicing throughput...")
    slice_with_copy(raw_bytes, CHUNK_SIZE)
    slice_zero_copy(raw_bytes, CHUNK_SIZE)
    
    # Cleanup
    if os.path.exists(FILE_NAME):
        os.remove(FILE_NAME)
```

#### Eksekusi dan Verifikasi
Jalankan langkah-langkah di terminal Anda:
```bash
python3 memory_profiler.py
python3 zero_copy_engine.py
```

*Expected Terminal Output (Nilai numerik dapat bervariasi bergantung hardware):*
```
Menjalankan benchmark alokasi untuk 500000 instansi...
[NormalPayload]
  Execution Time: 0.2815 detik
  Current Memory: 77.25 MB
  Peak Memory   : 77.28 MB
[SlottedPayload]
  Execution Time: 0.1982 detik
  Current Memory: 30.52 MB
  Peak Memory   : 30.54 MB
Menyiapkan 120MB binary file...
Memulai komparasi slicing throughput...
Standard Bytes Slicing: 0.0842 detik (Checksum: 15302912)
Zero-Copy Memoryview Slicing: 0.0381 detik (Checksum: 15302912)
```

---

### 13. Exercise

#### Level: Easy
1. Buat class `MetricPoint` dengan atribut `timestamp` (float), `metric_name` (str), dan `value` (float). 
2. Terapkan mekanisme `__slots__` pada kelas tersebut.
3. Tulis skrip verifikasi menggunakan `hasattr()` untuk membuktikan bahwa atribut dinamis baru di luar 3 atribut tersebut ditolak secara otomatis oleh interpreter (`AttributeError`).

#### Level: Medium
Buat sebuah kelas `CyclicNode` yang menyimpan referensi ke `next_node`.
1. Hubungkan `NodeA.next_node = NodeB` dan `NodeB.next_node = NodeA`.
2. Gunakan modul `weakref` pada referensi balik untuk memastikan `sys.getrefcount` tidak bertambah dan kedua objek dapat di-dealokasikan secara langsung oleh Reference Counting Engine tanpa intervensi pemindaian Generational GC.

#### Level: Hard
Kembangkan custom buffer stream parser bernama `RingBufferZeroCopy`:
1. Menerima `bytearray` dengan kapasitas sirkular tetap (misal: 1 MB).
2. Membaca stream bit mentah secara berkelanjutan tanpa realokasi heap.
3. Gunakan *slicing* `memoryview` untuk mengekstrak frame protokol tanpa pernah menyalin array data yang ada di heap.
4. Buat benchmark yang memvalidasi bahwa metrik alokasi memori snapshot `tracemalloc` menunjukkan 0 bytes alokasi baru selama proses ekstraksi 50.000 frame stream berlangsung.

---

### 14. Challenge (Enterprise Architectural Scenario)

**Skenario**:
Anda adalah Principal Core Infrastructure Engineer pada platform bursa aset kripto. Gateway Anda menerima pesan feed transaksi L2 Order Book dari node WebSocket upstream dengan volume **120.000 pesan biner per detik**.

Spesifikasi Server Worker:
* Alokasi RAM terbatas: 1 GB per kontainer k8s.
* Latensi pemrosesan p99 dibatasi maksimal $\le 10\text{ ms}$.

Kondisi Masalah Saat Ini:
* Parser biner berbasis `bytes` standar memicu `MemoryError` setelah 30 menit running akibat fragmentasi heap pada PyMalloc.
* Analisis memori menunjukkan generasi Gen 2 memegang jutaan objek parsial yang terlepas (*leaked references*) akibat *closure callbacks* pada library async I/O.
* Garbage collection stop-the-world freeze terjadi setiap 15 detik, menyebabkan drop koneksi socket WebSocket upstream.

**Tugas Tantangan**:
Rancang dan bangun prototipe modul **High-Throughput Ingestion Engine** yang memenuhi parameter berikut:
1. Mengeliminasi seluruh duplikasi alokasi memori heap pada layer pembacaan stream memanfaatkan `memoryview` atau *custom object pooling pattern*.
2. Memastikan tidak ada instance dictionary dinamis yang dibuat pada hot-path alur data transaksi.
3. Rancang strategi orkestrasi pembersihan `gc` secara non-blocking atau tersinkronisasi, sehingga proses pembersihan siklus referensi hanya terjadi di luar jendela *critical execution* transaksi.
4. Tulis program pengujian integrasi yang mengalirkan data secara kontinu selama minimal 2 menit dan buktikan dengan snapshot `tracemalloc` bahwa penggunaan heap memory tetap flat (*zero upward drift*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa fungsi utama dari field `ob_refcnt` yang didefinisikan pada struktur dasar CPython `PyObject`?
2. Pada skenario apa CPython menggunakan alokator internal PyMalloc dibandingkan langsung memanggil alokator sistem operasi (`malloc`)?
3. Mengapa sebuah integer sederhana bernilai `1` di Python 64-bit mengonsumsi 28 bytes memori, bukan 8 bytes?
4. Manfaat mendasar apa yang diperoleh dari penggunaan `__slots__` pada deklarasi class Python?
5. Mengapa manipulasi slicing `data[0:100]` pada objek `bytes` berukuran besar membutuhkan alokasi memori baru, sementara `memoryview(data)[0:100]` tidak?

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Jelaskan bagaimana *cyclic reference* dapat menggagalkan mekanisme *Reference Counting Engine* dalam membersihkan objek dari memori!
7. Kapan sebuah objek kontainer di CPython dipromosikan dari Generasi 0 ke Generasi 1 pada Generational Garbage Collector?
8. Apa peran field `ob_size` pada struktur `PyVarObject` dan sebutkan dua tipe data bawaan Python yang memanfaatkannya!
9. Apa konsekuensi teknis jika kita mencoba menambahkan weak reference (`weakref.ref()`) pada sebuah class yang mendefinisikan `__slots__` tanpa menyertakan slot `'__weakref__'`?
10. Mengapa pemanggilan `sys.getsizeof()` pada objek dictionary yang berisi satu juta data tidak mencerminkan total memori aktual yang dikonsumsi oleh pasangan *key-value* di dalamnya?

#### Bagian 3: Production Case Analysis (3 Kasus)
11. **Kasus 1**: Pada layanan API dengan beban tinggi, Anda melihat memori kontainer terus naik secara stabil (grafik linear ke atas tanpa pernah turun) hingga server mati terkena *OOMKilled*. Namun, hasil pemindaian `gc.garbage` menghasilkan list kosong `[]`. Apa kemungkinan besar akar masalahnya dan langkah diagnostik apa yang harus Anda lakukan?
12. **Kasus 2**: Sebuah microservice pemrosesan gambar memuat file biner 50 MB ke dalam variabel `bytes`, kemudian memecahnya menjadi ribuan sub-blok koordinat piksel untuk diproses oleh worker threads. Latensi service sangat buruk dan CPU usage tinggi pada alur pembagian gambar. Analisis letak inefisiensinya dan berikan solusi arsitekturalnya!
13. **Kasus 3**: Dalam pipeline *event streaming*, engineer senior memutuskan untuk mematikan GC sepenuhnya dengan memanggil `gc.disable()`. Hasilnya latensi p99 membaik drastis secara instan. Risiko arsitektural apa yang dihadapi oleh aplikasi tersebut dalam jangka panjang, dan proteksi teknis apa yang wajib diimplementasikan jika konfigurasi ini dipertahankan?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. `ob_refcnt` bertugas melacak jumlah referensi aktif yang sedang mengarah ke objek tersebut. Ketika nilai ini menyentuh angka 0, memori objek tersebut langsung dideallokasi seketika secara deterministik.
2. PyMalloc digunakan khusus untuk menangani alokasi objek berukuran kecil, yaitu $\le 512$ bytes, guna mencegah fragmentasi memori OS dan mempercepat alokasi via memory pool terstruktur.
3. Karena integer di Python adalah instansi `PyObject` penuh, yang mencakup 8 bytes untuk `ob_refcnt`, 8 bytes pointer `ob_type`, 8 bytes digit pointer/value representation, dan 4 bytes sizing metadata/alignment padding.
4. `__slots__` meniadakan pembuatan atribut dictionary internal (`__dict__`) pada setiap instansi, menggantikannya dengan array pointer statis berukuran tetap di level C, yang drastis menurunkan footprint memori objek.
5. Slicing pada `bytes` membuat objek baru dan menyalin seluruh array byte yang ditunjuk ($O(N)$ memory duplication), sedangkan `memoryview` mengimplementasikan Buffer Protocol (PEP 3118) yang hanya membuat wrapper pointer metadata baru ke memory buffer yang telah ada ($O(1)$ tanpa realokasi heap).

#### Bagian 2: Intermediate
6. Jika Objek A dan B saling mereferensikan satu sama lain, `ob_refcnt` keduanya minimal bernilai 1 meskipun seluruh variabel lokal program yang mengakses A dan B telah dihapus. Reference counter tidak pernah menyentuh 0, sehingga memori keduanya tidak pernah dibebaskan oleh reference counting engine.
7. Objek dipromosikan dari Gen 0 ke Gen 1 jika objek tersebut selamat (tidak terbukti menjadi unreachable cycle dan tidak memiliki refcount 0) setelah satu siklus pemindaian Garbage Collection pada Gen 0 selesai dieksekusi.
8. `ob_size` menyimpan jumlah item/elemen yang ditampung oleh variabel dinamis tersebut. Digunakan oleh tipe data berukuran dinamis seperti `list`, `tuple`, `bytes`, dan `str`.
9. Python akan melempar error `TypeError: cannot create weak reference to 'CustomClass' object` karena kelas berbasis `__slots__` tidak mengalokasikan ruang memori untuk pointer pelacakan weakref kecuali atribut string `'__weakref__'` dicantumkan secara eksplisit dalam definisi tuple `__slots__`.
10. `sys.getsizeof()` hanya menghitung ukuran tabel hash dictionary itu sendiri (bucket array pointer internal). Objek *key* dan objek *value* aktual berada pada lokasi memori heap terpisah dan tidak ditelusuri secara rekursif oleh fungsi tersebut.

#### Bagian 3: Production Case Analysis
11. **Solusi Kasus 1**: `gc.garbage` kosong menandakan tidak ada siklus referensi yang tidak terurai (*unresolvable cyclic reference*). Kebocoran kemungkinan besar terjadi akibat **Unintentional Reference Retention** pada level aplikasi: objek masih dianggap hidup oleh interpreter karena tersimpan di variabel global, class attribute, *long-lived cache* (seperti `functools.lru_cache` tanpa batas maxsize), atau terikat di dalam closure listener yang tidak pernah dilepas. Langkah diagnosis: Ambil snapshot alokasi memori berjarak 10 menit menggunakan modul `tracemalloc.take_snapshot()`, lalu jalankan `snapshot2.compare_to(snapshot1, 'lineno')` untuk melihat baris kode mana yang terus menerus menambah objek tanpa dealokasi.
12. **Solusi Kasus 2**: Inefisiensi terletak pada *memory thrashing* akibat slicing berulang pada tipe `bytes`. Memotong file 50 MB menjadi ribuan sub-blok array menghasilkan ribuan salinan array byte baru di memori heap, menyiksa PyMalloc dan System Malloc, serta memicu *cache thrashing* pada CPU. Solusi: Muat file ke dalam `bytearray` atau bungkus buffer file mentah menggunakan `memoryview`. Setiap thread worker harus menerima sub-slice `memoryview` (`view[offset:offset+chunk]`), sehingga seluruh worker beroperasi pada single allocated shared memory buffer tanpa ada realokasi memori baru.
13. **Solusi Kasus 3**: Risikonya adalah terjadinya penumpukan memori tak terbatas (*memory bloat / leak*) jika pada basis kode aplikasi terdapat kode yang secara tidak sengaja membentuk *cyclic references* (misalnya traceback exception, bound methods, graf node). Karena GC dinonaktifkan, siklus tersebut tidak akan pernah dideteksi dan dibersihkan oleh CPython. Proteksi teknis: (a) Jadwalkan eksekusi `gc.collect()` secara manual pada periode waktu tertentu di mana traffic sedang berada di titik terendah (*off-peak hours/idle loop*), (b) Lakukan audit kode ketat menggunakan `weakref` pada seluruh relasi referensi melingkar, dan (c) Implementasikan alerting cgroup memory limit di platform orkestrasi (k8s) untuk mendeteksi anomali konsumsi heap secara dini.

---

### 16. Summary

1. **CPython Memory Hierarchy**: Memori dikelola melalui segregasi bertingkat: *Arena (256 KB)* $\rightarrow$ *Pool (4 KB)* $\rightarrow$ *Block (8-512 Bytes)* via alokator internal **PyMalloc** untuk efisiensi alokasi objek kecil, sedangkan alokasi $> 512$ bytes dialihkan langsung ke alokator sistem operasi via **System Malloc**.
2. **Dual-Tier Garbage Collection**: Deallokasi deterministik instan dikelola via **Reference Counting** (`ob_refcnt == 0`), sementara pembersihan siklus referensi melingkar (*cyclic references*) didelegasikan kepada **Generational GC** berbasis heuristik umur (Gen 0, 1, 2) yang membawa konsekuensi *Stop-the-World pauses*.
3. **Optimasi State Menggunakan `__slots__`**: Menghilangkan overhead tabel hash dinamis `__dict__` per objek, menghemat alokasi memori hingga lebih dari 60%, mempercepat resolusi atribut, dan menjaga integritas instansi di lingkungan skala besar.
4. **Buffer Protocol & Zero-Copy**: Penggunaan `memoryview` dan `bytearray` membuka akses langsung ke raw memory buffer pointer di level C, meniadakan biaya latensi duplikasi memory copy ($O(1)$ vs $O(N)$) pada pipeline jaringan dan I/O biner throughput tinggi.
5. **Observabilitas Produksi**: Pengukuran shallow menggunakan `sys.getsizeof()` tidak memadai untuk sistem produksi; arsitektur yang tangguh mengandalkan instrumen profiling presisi seperti `tracemalloc`, inspeksi graf referensi objek, dan kalibrasi ambang batas alokasi garbage collection (`gc.set_threshold`).