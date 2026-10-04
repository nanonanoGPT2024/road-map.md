# MODUL: BASIS DATA & SISTEM PENYIMPANAN
# SUB-MODUL 01: ARSITEKTUR ENGINE BASIS DATA DAN REKAYASA PENYIMPANAN FISIK (STORAGE ENGINE FOUNDATIONS)

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `CS-FND-07-01`
* **Nama Modul**: Arsitektur Engine Basis Data, Representasi Data Disk, dan Organisasi Halaman (*Storage Engine Foundations*)
* **Kategori**: `01-Core-Foundations`
* **Prasyarat**: 
  * `CS-FND-01-03` (Representasi Data & Sistem Bilangan Tingkat Rendah)
  * `CS-FND-03-02` (Arsitektur Sistem Operasi: Memori Virtual & File System I/O)
  * Pemahaman mendalam mengenai pointer, alokasi memori heap, dan manipulasi *byte-level* (C/Rust/Python struct).
* **Estimasi Waktu Belajar**: 8 - 10 Jam Kerja Efektif

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis (C4)** dekonstruksi arsitektur *Database Management System* (DBMS) multi-lapis, memetakan alur eksekusi dari parsing query hingga persistensi I/O pada subsistem penyimpanan.
2. **Mengevaluasi (C5)** kegagalan abstraksi *Operating System File System* dan `mmap` untuk kebutuhan ACID transaksi basis data transaksional intensif.
3. **Merancang (C6)** struktur fisik disk berorientasi blok (*Page Layout*) menggunakan paradigma *Slotted-Page Architecture* guna menangani variasi data bertipe tetap (*fixed-length*) dan dinamis (*variable-length*).
4. **Mengimplementasikan (C3)** mekanisme serialisasi baris (*tuple serialization*) biner tingkat rendah lengkap dengan penanganan *null bitmap*, *header*, dan penyelarasan memori (*memory alignment/padding*).
5. **Menghitung (C4)** efisiensi densitas penyimpanan (*storage density*), fragmentasi internal, dan *I/O cost model* dari pembacaan data disk.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Klien / Aplikasi]
       │
       ▼ (SQL Query / Protocol)
┌────────────────────────────────────────────────────────┐
│                   DBMS FRONTEND ENGINE                 │
│  [Parser] ──> [Binder] ──> [Optimizer] ──> [Executor]  │
└──────────────────────────┬─────────────────────────────┘
                           │ Plan Nodes (Iterators/Volcano)
                           ▼
┌────────────────────────────────────────────────────────┐
│                   STORAGE ENGINE                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │               BUFFER POOL MANAGER                │  │
│  │   [Frame Table] <───> [Replacement Policy: LRU]  │  │
│  └──────────────────────────┬───────────────────────┘  │
│                             │ Fetch/Flush Page         │
│  ┌──────────────────────────▼───────────────────────┐  │
│  │                   DISK MANAGER                   │  │
│  │   [Page Allocator] <───> [OS System Calls]       │  │
│  └──────────────────────────┬───────────────────────┘  │
└─────────────────────────────┼──────────────────────────┘
                              │ O_DIRECT / File I/O
                              ▼
┌────────────────────────────────────────────────────────┐
│                PERSISTENT STORAGE (DISK)               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Page 0 (Header) │ Page 1 (Data) │ Page 2 (Data)  │  │
│  │ ┌──────────────────────────────────────────────┐ │  │
│  │ │ [Page Header] [Slot Array ->]                │ │  │
│  │ │                 [<- FREE SPACE ->]           │ │  │
│  │ │ [<- Tuple Data (Attributes, Variable-Length)]│ │  │
│  │ └──────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem basis data enterprise modern tidak memperlakukan disk sebagai berkas teks biasa atau mengandalkan abstraction layer default dari sistem operasi (*OS filesystem cache*). Kesalahan pemahaman fundamental arsitektur fisik ini menyebabkan aplikasi mengalami latensi I/O tinggi, fragmentasi masif, hingga korupsi data saat sistem mengalami *abrupt failure* (mati listrik).

1. **Kontrol Deterministik Durabilitas (ACID)**: Basis data relasional memerlukan garansi penulisan berurutan melalui *Write-Ahead Logging* (WAL). Mengandalkan OS cache (`fsync` acak) menghilangkan determinisme kapan data benar-benar menetap (*flushed*) di piringan magnetik atau sel silikon NAND flash.
2. **Keterbatasan `mmap`**: Meski populer, menggunakan *memory-mapped files* (`mmap`) menyerahkan keputusan penggusuran halaman (*page eviction*) ke kernel sistem operasi yang tidak memahami semantik query database, memicu terjadinya *stall* tak terduga (*I/O page fault lock contention*).
3. **Optimasi Bandwidth I/O**: Akses disk berkisar antara 100 hingga 1.000.000 kali lebih lambat dibanding akses register atau cache L1 CPU. Desain tata letak halaman yang buruk membuang transfer rate I/O disk untuk membaca *metadata overhead* alih-alih data faktual.

---

## SEKSI 05 — APA ITU (WHAT)

**DBMS Storage Engine** adalah komponen perangkat lunak modular yang bertanggung jawab langsung atas alokasi ruang, representasi data pada media persisten non-volatile, serta manipulasi *in-memory representation* data ketika dieksekusi oleh query engine.

Secara fisik, disk dipecah menjadi unit terkecil penulisan dan pembacaan yang disebut **Page** (biasanya berukuran tetap: 4KB, 8KB, atau 16KB; PostgreSQL menggunakan 8KB, MySQL InnoDB menggunakan 16KB). Database engine mengelola koleksi *page* ini tanpa memedulikan representasi file sistem operasi menggunakan abstraksi **Slotted-Page Architecture**.

### Anatomi Komponen Utama:
* **Disk Manager**: Mengabstraksikan file sistem operasi menjadi kumpulan halaman berurutan (*logical pages*), mengatur penambahan halaman baru (*allocation*), dan daur ulang ruang kosong.
* **Buffer Pool Manager**: Ruang memori (RAM) terorganisasi dalam struktur array *frames* yang menampung representasi byte-level dari page fisik disk.
* **Slotted Page**: Format pengorganisasian di dalam sebuah halaman individual di mana *header* melacak pointer slot secara maju (*grow forward*), sementara data rekaman riil (*tuple*) ditulis dari bagian belakang halaman mundur ke depan (*grow backward*).
* **Record Identifier (RID/TID)**: Penanda unik global bagi suatu rekaman dalam disk, tersusun secara deterministik atas format `[Page_ID, Slot_Offset]`.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Dekomposisi Slotted-Page Layout

Sebuah *Page* tidak diperlakukan sebagai *stream* linear, melainkan dipartisi menjadi empat segmen kritis:
* **Page Header**: Memuat metadata halaman (misal: LSN untuk pemulihan crash, *free space pointer*, jumlah slot, checksum).
* **Slot Array (Indirection Layer)**: Array yang tumbuh dari awal halaman (setelah header) ke arah bawah. Tiap elemen slot berisi dua atribut integer: `(offset_ke_tuple, ukuran_tuple)`.
* **Free Space Window**: Ruang kosong tak teralokasi yang terletak di antara ujung akhir slot array dan awal data tuple fisik.
* **Tuple Storage**: Ruang alokasi rekaman fisik yang tumbuh dari batas akhir halaman (misal: offset 4096 atau 8192) bergerak mundur ke atas mendekati slot array.

```
+-----------------------------------------------------------------------+
|  PAGE HEADER  | SLOT 0 | SLOT 1 | SLOT 2 | ...                        |
|  (Fixed Size) | (Off,Len) (Off,Len) ...  |                            |
+---------------+--------------------------+                            |
|                     ===> FREE SPACE GAP <===                          |
|                                                                       |
+-----------------------------------------------------------------------+
| ... | TUPLE 2 DATA | TUPLE 1 DATA             | TUPLE 0 DATA          |
+-----------------------------------------------------------------------+
```

### 2. Anatomi Internal Tuple Fisik

Data tidak disimpan mentah berdampingan tanpa metadata. Tiap tuple membawa struktur biner standar:
1. **Tuple Header**:
   * Jumlah atribut/kolom.
   * **Null Bitmap**: Array bit terkompresi yang mengindikasikan apakah suatu kolom bernilai `NULL` (menghindari alokasi byte untuk data nihil).
2. **Fixed-Length Attributes**: Kolom dengan ukuran pasti (misal: `INT32`, `INT64`, `TIMESTAMP`, `DOUBLE`) diposisikan langsung berdasarkan offset kumulatif statis.
3. **Variable-Length Offset Table**: Pointer relatif dan panjang data dinamis untuk atribut seperti `VARCHAR` atau `BLOB`.
4. **Variable-Length Attributes Payload**: Data teks atau biner arbitrer diletakkan di akhir struktur tuple.

### 3. Eksekusi Mutasi: Operasi Hapus (*Deletion*) dan Kompaksi

Saat sebuah tuple dihapus:
1. Entry slot yang bersangkutan pada *Slot Array* tidak dihapus dari array secara fisik (karena akan merusak indeks RID dari baris lain), melainkan ditandai dengan flag khusus (misal: `Offset = 0` atau `Length = TOMBSTONE`).
2. Ruang yang ditinggalkan oleh data tuple pada *Tuple Storage* menjadi *fragmented free space*.
3. Database tidak langsung memindahkan tuple lain secara real-time pada saat *read*, melainkan melakukan **Defragmentasi/Kompaksi** internal ketika alokasi data baru membutuhkan blok kontigu yang lebih besar daripada celah *free space window*. Tuple yang aktif digeser merapat ke batas bawah halaman, dan *offset* pada *Slot Array* diperbarui secara atomik.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

```
========================================================================================
STRUKTUR FISIK BINARY SLOTTED PAGE (CONTOH UKURAN 4096 BYTE / 0x1000)
========================================================================================

Offset Hex   Offset Dec    Struktur Konten                                 Arah Pertumbuhan
----------------------------------------------------------------------------------------
0x0000       0000          +--------------------------------------------+
                           | PAGE HEADER (Ukuran: 24 Byte)              |
                           | - Page LSN:           uint64 (8 bytes)     |
                           | - Free Space Pointer: uint16 (2 bytes)     |
                           | - Slot Count:         uint16 (2 bytes)     |
                           | - Flags / Checksum:   uint32 (4 bytes)     |
                           | - Reserved:           uint64 (8 bytes)     |
0x0018       0024          +--------------------------------------------+
                           | SLOT ARRAY (Indirection Vector)            |
                           | Slot 0: [Offset: 0x0F00 | Len: 256 bytes]  |    |
                           | Slot 1: [Offset: 0x0DA0 | Len: 352 bytes]  |    | Bertumbuh
                           | Slot 2: [Offset: 0x0CA0 | Len: 256 bytes]  |    V ke Bawah
0x0030       0048          + - - - - - - - - - - - - - - - - - - - - - -+
                           |                FREE SPACE                  |
                           |                                            |
                           |    (Jarak antara batas akhir Slot Array    |
                           |     dan Free Space Pointer = Ruang Bebas)  |
                           |                                            |
0x0CA0       3232          + - - - - - - - - - - - - - - - - - - - - - -+
                           | TUPLE 2 DATA                               |    ^ Bertumbuh
0x0DA0       3488          +--------------------------------------------+    | ke Atas
                           | TUPLE 1 DATA                               |    |
0x0F00       3840          +--------------------------------------------+
                           | TUPLE 0 DATA                               |
0x1000       4096          +--------------------------------------------+ (Batas Akhir)

========================================================================================
STRUKTUR INTERNAL TUPLE 0 (BINARY LEVEL LAYOUT)
========================================================================================

Offset Relatif   Isi Komponen                             Penjelasan
----------------------------------------------------------------------------------------
0x00 - 0x03      TUPLE HEADER: Attributes Count (uint16)  Jumlah total field: 3
                 TUPLE HEADER: Flags            (uint16)  Tipe: Active / Tombstone
0x04 - 0x04      NULL BITMAP (uint8)                      Bit 0: Col 0 Null? (0 = No)
                                                          Bit 1: Col 1 Null? (0 = No)
                                                          Bit 2: Col 2 Null? (1 = Yes)
0x05 - 0x07      MEMORY ALIGNMENT PADDING                 Penyelarasan ke batas 4/8-byte
0x08 - 0x0F      COL 0: id (INT64)                        Data numerik bernilai 1001
0x10 - 0x13      COL 1: string_len (uint16) + offset      Offset ke payload teks: 0x14
0x14 - 0x3F      COL 1 PAYLOAD: name ("DATABASE")         Data string berukuran dinamis
0x40 - 0x40      COL 2: (KOSONG - TERCATAT PADA BITMAP)   Tidak ada byte dialokasikan!
========================================================================================
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi serialisasi biner tuple sederhana menggunakan bahasa Python murni melalui pustaka modular bawaan `struct`, yang mereplikasi bagaimana tuple baris dikodekan ke dalam representasi byte array tingkat rendah tanpa pustaka pihak ketiga.

```python
import struct

# Definisi:
# Kolom:
# 0: id (uint32)
# 1: is_active (bool/uint8)
# 2: balance (float64)
# 3: username (varchar - variable length)

def serialize_tuple(user_id: int, is_active: bool, balance: float, username: str) -> bytes:
    encoded_name = username.encode('utf-8')
    name_len = len(encoded_name)
    
    # 1. Header (Tuple Length: uint16, Attribute Count: uint16)
    attr_count = 4
    
    # 2. Null Bitmap (1 byte cukup untuk menampung 8 atribut)
    null_bitmap = 0b00000000  # Tidak ada yang NULL
    
    # 3. Serialisasi Fixed-Length Attributes
    # Formatter: > (Big Endian), H (uint16), B (uint8), d (float64)
    fixed_part = struct.pack(">IBd", user_id, 1 if is_active else 0, balance)
    
    # 4. Simpan Offset Relatif untuk Variable-Length
    # Variable length pointer: length (uint16)
    var_header = struct.pack(">H", name_len)
    
    # Total ukuran payload
    header_size = struct.calcsize(">HHB")
    total_len = header_size + len(fixed_part) + len(var_header) + name_len
    
    # Bundle header
    header = struct.pack(">HHB", total_len, attr_count, null_bitmap)
    
    # Rakit seluruh byte array
    return header + fixed_part + var_header + encoded_name

def deserialize_tuple(data: bytes):
    # Parsing Header
    total_len, attr_count, null_bitmap = struct.unpack_from(">HHB", data, 0)
    offset = struct.calcsize(">HHB")
    
    # Parsing Fixed-Length
    user_id, is_active_int, balance = struct.unpack_from(">IBd", data, offset)
    offset += struct.calcsize(">IBd")
    
    # Parsing Variable-Length
    name_len = struct.unpack_from(">H", data, offset)[0]
    offset += struct.calcsize(">H")
    
    username = data[offset : offset + name_len].decode('utf-8')
    
    return {
        "id": user_id,
        "is_active": bool(is_active_int),
        "balance": balance,
        "username": username
    }

# Eksekusi
raw_bytes = serialize_tuple(101, True, 1250000.75, "satria_wicaksana")
print(f"Total Bytes Disimpan: {len(raw_bytes)}")
print(f"Raw Hex: {raw_bytes.hex()}")

parsed = deserialize_tuple(raw_bytes)
print(f"Hasil Ekstraksi: {parsed}")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi berorientasi objek kelas industri dari **Slotted-Page Storage Manager** yang beroperasi pada blok biner murni (`bytearray`) berukuran tetap 4096 byte. Engine ini mendukung *insertion*, penandaan penghapusan (*tombstone*), pengaksesan berbasis *Record Identifier (RID)*, dan kompaksi fragmentasi memori.

```python
import struct
from typing import Optional, Tuple

class SlottedPage:
    PAGE_SIZE = 4096
    PAGE_HEADER_FORMAT = ">HHH" # Free Space Pointer (uint16), Slot Count (uint16), Flags (uint16)
    PAGE_HEADER_SIZE = struct.calcsize(PAGE_HEADER_FORMAT)
    
    SLOT_ENTRY_FORMAT = ">HH"   # Tuple Offset (uint16), Tuple Length (uint16)
    SLOT_ENTRY_SIZE = struct.calcsize(SLOT_ENTRY_FORMAT)
    
    TOMBSTONE_OFFSET = 0xFFFF   # Sentinel untuk menandakan slot terhapus
    
    def __init__(self, raw_bytes: Optional[bytearray] = None):
        if raw_bytes is None:
            self.data = bytearray(self.PAGE_SIZE)
            # Awalnya, free space pointer berada di batas paling akhir halaman
            self.free_space_ptr = self.PAGE_SIZE
            self.slot_count = 0
            self.flags = 0
            self._flush_header()
        else:
            if len(raw_bytes) != self.PAGE_SIZE:
                raise ValueError("Data harus tepat berukuran 4096 byte.")
            self.data = raw_bytes
            self.free_space_ptr, self.slot_count, self.flags = struct.unpack_from(
                self.PAGE_HEADER_FORMAT, self.data, 0
            )

    def _flush_header(self):
        struct.pack_into(
            self.PAGE_HEADER_FORMAT, 
            self.data, 
            0, 
            self.free_space_ptr, 
            self.slot_count, 
            self.flags
        )

    def get_free_contiguous_space(self) -> int:
        """Menghitung ruang kosong absolut antara Slot Array dan Tuple Storage."""
        used_by_slots = self.PAGE_HEADER_SIZE + (self.slot_count * self.SLOT_ENTRY_SIZE)
        return self.free_space_ptr - used_by_slots

    def insert_record(self, record_data: bytes) -> Optional[int]:
        """
        Memasukkan record ke dalam slotted page.
        Returns: Slot ID (integer) atau None jika ruang tidak mencukupi.
        """
        record_len = len(record_data)
        required_space = record_len + self.SLOT_ENTRY_SIZE
        
        if self.get_free_contiguous_space() < required_space:
            # Mencoba mengecek apakah memungkinkan jika dilakukan defragmentasi
            self.defragment()
            if self.get_free_contiguous_space() < required_space:
                return None  # Benar-benar kehabisan ruang (Page Full)

        # 1. Alokasikan data dari belakang (Tuple Storage grow backward)
        new_tuple_offset = self.free_space_ptr - record_len
        self.data[new_tuple_offset : new_tuple_offset + record_len] = record_data
        
        # 2. Update status Free Space Pointer
        self.free_space_ptr = new_tuple_offset
        
        # 3. Gunakan slot yang tersedia atau buat slot baru di akhir array
        target_slot_id = self.slot_count
        for slot_idx in range(self.slot_count):
            slot_offset_pos = self.PAGE_HEADER_SIZE + (slot_idx * self.SLOT_ENTRY_SIZE)
            offset, _ = struct.unpack_from(self.SLOT_ENTRY_FORMAT, self.data, slot_offset_pos)
            if offset == self.TOMBSTONE_OFFSET:
                target_slot_id = slot_idx
                break
                
        slot_pos = self.PAGE_HEADER_SIZE + (target_slot_id * self.SLOT_ENTRY_SIZE)
        struct.pack_into(self.SLOT_ENTRY_FORMAT, self.data, slot_pos, new_tuple_offset, record_len)
        
        if target_slot_id == self.slot_count:
            self.slot_count += 1
            
        self._flush_header()
        return target_slot_id

    def read_record(self, slot_id: int) -> Optional[bytes]:
        """Mengambil data record biner berdasarkan Slot ID."""
        if slot_id < 0 or slot_id >= self.slot_count:
            return None
            
        slot_pos = self.PAGE_HEADER_SIZE + (slot_id * self.SLOT_ENTRY_SIZE)
        offset, length = struct.unpack_from(self.SLOT_ENTRY_FORMAT, self.data, slot_pos)
        
        if offset == self.TOMBSTONE_OFFSET:
            return None # Rekaman telah dihapus (Tombstone)
            
        return bytes(self.data[offset : offset + length])

    def delete_record(self, slot_id: int) -> bool:
        """Menandai tuple sebagai dihapus secara logis."""
        if slot_id < 0 or slot_id >= self.slot_count:
            return False
            
        slot_pos = self.PAGE_HEADER_SIZE + (slot_id * self.SLOT_ENTRY_SIZE)
        offset, _ = struct.unpack_from(self.SLOT_ENTRY_FORMAT, self.data, slot_pos)
        
        if offset == self.TOMBSTONE_OFFSET:
            return False # Sudah dihapus sebelumnya
            
        # Set slot sebagai tombstone, panjang diubah menjadi 0
        struct.pack_into(self.SLOT_ENTRY_FORMAT, self.data, slot_pos, self.TOMBSTONE_OFFSET, 0)
        return True

    def defragment(self):
        """
        Kompaksi fisik: Memindahkan semua record aktif ke tepi paling bawah halaman
        untuk menghilangkan lubang-lubang fragmentasi (gap).
        """
        active_records = []
        for slot_idx in range(self.slot_count):
            slot_pos = self.PAGE_HEADER_SIZE + (slot_idx * self.SLOT_ENTRY_SIZE)
            offset, length = struct.unpack_from(self.SLOT_ENTRY_FORMAT, self.data, slot_pos)
            if offset != self.TOMBSTONE_OFFSET:
                data = bytes(self.data[offset : offset + length])
                active_records.append((slot_idx, data))

        # Reset penunjuk free space kembali ke akhir halaman
        current_offset = self.PAGE_SIZE
        
        # Tulis ulang record secara kontigu dari ujung kanan (bawah)
        for slot_idx, record_data in active_records:
            current_offset -= len(record_data)
            self.data[current_offset : current_offset + len(record_data)] = record_data
            
            # Perbarui pointer pada slot yang bersangkutan
            slot_pos = self.PAGE_HEADER_SIZE + (slot_idx * self.SLOT_ENTRY_SIZE)
            struct.pack_into(
                self.SLOT_ENTRY_FORMAT, 
                self.data, 
                slot_pos, 
                current_offset, 
                len(record_data)
            )

        self.free_space_ptr = current_offset
        self._flush_header()

# Demo Alur Operasional Mesin
if __name__ == "__main__":
    page = SlottedPage()
    
    # 1. Insert 3 Record
    rid0 = page.insert_record(b"DATA_TRANSAKSI_001_NILAI_RP_50000")
    rid1 = page.insert_record(b"DATA_TRANSAKSI_002_NILAI_RP_7500000")
    rid2 = page.insert_record(b"DATA_TRANSAKSI_003_NILAI_RP_1200")
    
    print(f"Slot Terbuat: RID={rid0}, RID={rid1}, RID={rid2}")
    print(f"Sisa Ruang Kontigu: {page.get_free_contiguous_space()} bytes")
    
    # 2. Hapus Rekaman Tengah (RID 1)
    page.delete_record(rid1)
    print(f"RID 1 Dihapus. Verifikasi Read: {page.read_record(rid1)}")
    
    # 3. Kompaksi Memori
    page.defragment()
    print(f"Sisa Ruang Kontigu Pasca Defragmentasi: {page.get_free_contiguous_space()} bytes")
    
    # 4. Validasi Integritas Data RID 0 dan 2
    assert page.read_record(rid0) == b"DATA_TRANSAKSI_001_NILAI_RP_50000"
    assert page.read_record(rid2) == b"DATA_TRANSAKSI_003_NILAI_RP_1200"
    print("Integritas data terverifikasi sempurna pasca-defragmentasi.")
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | N-ary Storage Model (NSM / Row Store) | Decomposition Storage Model (DSM / Column Store) |
| :--- | :--- | :--- |
| **Tata Letak Fisik** | Tuple disimpan utuh secara horizontal dalam 1 halaman. | Setiap kolom dipisah dan disimpan di set halaman berbeda. |
| **Kelebihan Utama** | Sangat cepat untuk operasi OLTP (Insert/Update/Delete cepat, *point lookups* berbasis RID). | Sangat cepat untuk analitik OLAP (agregasi `SUM`, `AVG` pada jutaan data tanpa memuat kolom tak relevan). |
| **Kekurangan** | *I/O Waste*: Membaca seluruh atribut baris meski query hanya meminta satu atribut (`SELECT age FROM users`). | Biaya rekonstruksi baris (*tuple stitching*) sangat mahal saat melakukan operasi transaksi individual. |
| **Tingkat Kompresi** | Rendah: Tipe data heterogen dalam satu halaman membatasi efisiensi algoritma kompresi. | Ekstrem: Nilai data homogen dalam satu halaman memungkinkan Run-Length Encoding (RLE) atau Dictionary Compression. |

### Memori Operasional: In-Place Updates vs Out-of-Place Updates
* **In-Place (Slotted Page / B-Tree Tradisional)**: Mengubah isi record langsung di lokasi byte aslinya.
  * *Trade-off*: Efisien memori, namun variasi panjang string baru yang lebih panjang memicu pemecahan halaman (*page splits*) atau fragmentasi berat.
* **Out-of-Place (Log-Structured Merge / Append-Only)**: Modifikasi dilakukan dengan menambahkan versi baru data ke ujung log (*append-only*), membatalkan entri lama melalui *compaction* latar belakang.
  * *Trade-off*: Throughput *write* sangat tinggi (karena sekuensial), namun membutuhkan pembacaan multi-versi (*amplified read latency*).

---

## SEKSI 11 — BEST PRACTICES

1. **Sinkronisasi Sektor Perangkat Keras**: Ukuran halaman basis data harus merupakan kelipatan bulat dari ukuran sektor fisik perangkat penyimpanan (misal: 4KB untuk *Advanced Format* 4Kn Drives). Kegagalan sinkronisasi memicu *torn writes* dan *read-modify-write penalty*.
2. **Memory Alignment**: Selaraskan atribut biner dalam struktur record dengan kelipatan arsitektur CPU (4-byte untuk 32-bit integer, 8-byte untuk double/64-bit integer). Pengabaian alignment menyebabkan *misaligned memory access penalty* pada arsitektur x86/ARM.
3. **Penyimpanan Nilai Ekstrem Secara *Out-of-Line* (TOAST / Overflow Pages)**: Jika atribut variable-length melebihi proporsi aman dari halaman (misal: teks 64KB pada halaman 8KB), sistem penyimpanan wajib memecah data tersebut ke dalam rantai *Overflow Pages* terpisah, menyisakan *24-byte pointer descriptor* pada tuple utama.
4. **Isolasi Logika Slot Indirection**: Jangan pernah membiarkan komponen *query engine* tingkat atas memegang pointer memori mentah (`void*`) ke data record di disk. Komponen eksekusi hanya boleh memegang identifier abstrak `RID(Page_ID, Slot_Index)` demi memungkinkan *Buffer Pool* memindahkan halaman secara dinamis.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Mengasumsikan File `append` Sederhana Bersifat Crash-Safe**: Memanggil fungsi `write()` bahasa pemrograman tidak langsung melempar data ke media magnetik/silikon. Tanpa koordinasi eksplisit `O_DIRECT`, `F_FULLFSYNC`, atau `fsync()`, kegagalan daya mendadak akan menyisakan *corrupted page* dengan separuh data baru dan separuh data sampah (*torn page*).
2. **Kompaksi Terlalu Agresif Secara Inline**: Menjalankan defragmentasi halaman pada setiap instruksi `DELETE` secara synchronous. Kompaksi memindahkan ratusan byte dalam RAM, memicu *CPU cache invalidation* masif. Kompaksi idealnya ditunda secara lazy hingga ada penulisan baru yang membutuhkan kapasitas tersebut.
3. **Menyimpan Nilai NULL Sebagai Spasi Kosong atau Zero Bytes**: Mengalokasikan 4 byte integer bernilai `0` untuk merepresentasikan database `NULL`. Pendekatan yang benar adalah menggunakan **Null Bitmap Header** yang hanya memakan biaya 1 bit per kolom, menghemat persentase I/O disk secara masif pada skala miliaran data.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Level 1: Analisis Ukuran Record dan Densitas (Teoretis & Perhitungan)
Sebuah tabel memiliki skema sebagai berikut:
* `id`: `INT64` (8 byte)
* `age`: `INT16` (2 byte)
* `salary`: `FLOAT64` (8 byte)
* `is_verified`: `BOOL` (1 byte)

Asumsikan sistem database menggunakan halaman berukuran **4096 byte**, dengan *Page Header* berukuran **32 byte**, dan *Slot Entry* berukuran **4 byte**.
1. Hitung total ukuran 1 record jika *Tuple Header* membutuhkan **4 byte** (termasuk null bitmap)!
2. Abaikan padding/alignment, berapa jumlah record maksimal yang dapat dimuat secara absolut di dalam satu halaman slotted-page?
3. Jika terdapat *padding alignment* ke kelipatan 8 byte, hitung ulang kapasitas tampung maksimum per halaman!

### Level 2: Ekstensi Fitur Slotted-Page (Coding Hands-on)
Ambil kode implementasi dari **Seksi 09** dan modifikasi untuk menambahkan fungsionalitas berikut:
* Tambahkan mekanisme **Update Record In-Place**:
  * Jika panjang data baru $\le$ data lama, timpa langsung di tempat tanpa menggeser pointer tuple lain.
  * Jika panjang data baru $>$ data lama, tandai slot lama sebagai *tombstone* atau lakukan defragmentasi dan alokasikan di ruang free space baru dengan mempertahankan `Slot ID` yang sama.

### Level 3: Deteksi dan Pemulihan Torn Page (Integrasi Lanjut)
Rancang struktur *checksum* halaman:
* Tambahkan field `checksum: uint32` pada header halaman menggunakan modul `zlib.crc32`.
* Simpan bit checksum pada saat halaman ditandai bersih (*dirty page flushed*).
* Buat skenario pengujian di mana 512 byte terakhir halaman diganti dengan byte acak (mensimulasikan *abrupt hardware failure* saat penulisan), lalu pastikan kode Anda mampu melempar *exception CorruptedPageError* sebelum data sempat dibaca oleh layer query execution.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

### Pertanyaan Evaluasi

1. **Mengapa *Slotted-Page Architecture* menggunakan pointer slot yang tumbuh ke arah bawah dan data tuple yang tumbuh ke arah atas saling berlawanan?**
   * A. Untuk menghemat konsumsi register CPU saat loop iterasi record.
   * B. Agar ruang kosong (*free space*) terkonsentrasi di tengah, memungkinkan penambahan slot baru atau record baru secara dinamis tanpa partisi ulang ukuran.
   * C. Mencegah fragmentasi pada file log pemulihan (WAL).
   * D. Karena instruksi komparasi memori x86 bekerja mundur secara default.

2. **Apa peran teknis paling mendasar dari *Indirection Layer* (Slot Array) terhadap nilai Record Identifier (RID)?**
   * A. Memungkinkan kompresi data string secara run-length.
   * B. Mengizinkan pemindahan fisik lokasi tuple di dalam halaman (saat kompaksi) tanpa mengubah nilai RID yang menjadi acuan foreign key atau indeks sekunder.
   * C. Menghitung checksum otomatis pada level baris.
   * D. Mengamankan tuple dari akses concurrent transaction tanpa locking.

3. **Manakah konsekuensi arsitektural jika database enterprise hanya mengandalkan abstraction layer `mmap` milik OS kernel daripada mengimplementasikan *Buffer Pool Manager* kustom?**
   * A. Database tidak akan mampu menyimpan tipe data string berukuran dinamis.
   * B. OS kernel dapat sewaktu-waktu menulis (*flush*) dirty page ke disk tanpa memperhatikan urutan commit pada *Write-Ahead Log* (WAL), menghancurkan konsistensi transaksi (ACID).
   * C. DBMS tidak dapat membuat indeks pohon B+ Tree.
   * D. Kapasitas maksimum penyimpanan basis data dibatasi oleh panjang register prosesor 32-bit.

4. **Bagaimana keberadaan *Null Bitmap* pada *Tuple Header* meningkatkan performa I/O secara sistemik?**
   * A. Mempercepat kalkulasi enkripsi data di piringan magnetik.
   * B. Mengurangi komputasi CPU dalam mengevaluasi tipe data primitif.
   * C. Menghilangkan kebutuhan alokasi byte data secara fisik untuk kolom berstatus null, memperkecil ukuran tuple, dan memaksimalkan jumlah tuple per halaman.
   * D. Menjadikan skema relasional tabel berubah menjadi skema dokumen JSON secara otomatis.

5. **Kapan kondisi sebuah halaman (*Page*) diklasifikasikan membutuhkan proses defragmentasi internal?**
   * A. Segera setelah ada 1 record yang dibaca oleh query SELECT.
   * B. Saat slot array terisi penuh hingga nilai batas 65535.
   * C. Ketika ruang kosong kontigu (*contiguous free space gap*) tidak cukup menampung tuple baru, tetapi total ruang kosong kumulatif (termasuk ruang sampah *tombstone*) mencukupi.
   * D. Ketika ukuran file basis data di sistem operasi menyentuh batas 2 Gigabyte.

---

### Kunci Jawaban & Rasionalisasi

1. **Jawaban: B**
   * *Rasionalisasi*: Pertumbuhan konvergen (menuju ke tengah) memastikan fleksibilitas maksimal; kita tidak perlu memprediksi berapa jumlah baris atau berapa ukuran rata-rata baris sebelum halaman tersebut terisi penuh. Ruang sisa adalah milik bersama.
2. **Jawaban: B**
   * *Rasionalisasi*: Indirection memisahkan alamat fisik (offset memori) dari alamat logis (RID). B-Tree Index hanya merujuk pada `RID(Page_ID, Slot_Index)`. Jika posisi memori tuple bergeser 100 byte akibat defragmentasi, indeks luar tidak perlu diperbarui karena `Slot_Index`-nya konstan.
3. **Jawaban: B**
   * *Rasionalisasi*: Kernel OS hanya mengetahui blok memori, bukan transaksi DBMS. Jika OS memutuskan mengekspulsi memori kotor (*dirty page*) yang transaksinya belum di-commit ke disk mendahului log persistensi, pemulihan data pasca crash (*crash recovery*) mustahil dilakukan.
4. **Jawaban: C**
   * *Rasionalisasi*: Menyimpan 0 byte untuk atribut null secara nyata mengurangi jejak biner (*binary footprint*). Densitas tuple per page meningkat, menurunkan total transfer blok I/O yang harus dibaca dari disk secara drastis.
5. **Jawaban: C**
   * *Rasionalisasi*: Fragmentasi internal menghasilkan celah-celah kecil non-kontigu. Jika ruang bebas terkumpul secara utuh melalui pergeseran biner (kompaksi), tuple baru dapat masuk tanpa harus memicu pembuatan halaman baru (*page split/page allocation*).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Referensi**:
  * Ramakrishnan, R., & Gehrke, J. (2002). *Database Management Systems (3rd ed.)*. McGraw-Hill. (Bab 9: *Storing Data: Disks and Files*).
  * Petrov, Alex. (2019). *Database Internals: A Deep Dive into How Distributed Data Systems Work*. O'Reilly Media. (Bab 1: *Storage Engines*, Bab 2: *B-Tree Basics and Page Anatomy*).
  * Garcia-Molina, H., Ullman, J. D., & Widom, J. (2008). *Database Systems: The Complete Book (2nd ed.)*. Prentice Hall.
* **Paper Ilmiah Fundamental**:
  * Stonebraker, M., et al. (1981). *Operating System Support for Database Management*. Communications of the ACM, 24(7), 412–418. (Paper klasik yang mengupas kegagalan fitur OS untuk DBMS).
  * Graefe, G. (1994). *Volcano—An Extensible and Efficient Query Evaluation System*. IEEE Transactions on Knowledge and Data Engineering.
* **Materi Universitas Terbuka**:
  * CMU 15-445/645: *Database Systems* oleh Prof. Andy Pavlo (Carnegie Mellon University), Kuliah 01-04: *Storage Engine Architecture*.
* **Repositori & Dokumentasi Kode Sumber**:
  * PostgreSQL Source Code: `src/backend/storage/page/bufpage.c` (Implementasi nyata Page Layout PostgreSQL).
  * SQLite Source Code: `src/btree.c` (Implementasi B-Tree dan Slotted-Page yang sangat elegan dan ringkas).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Storage Engine adalah pondasi terbawah basis data yang menjembatani struktur data logis (tabel, relasi) dengan realitas fisik perangkat keras penyimpanan (blok non-volatile).
2. Sistem operasi *file caching* dan `mmap` tidak memadai untuk garansi persistensi transaksi ACID, sehingga DBMS wajib memanipulasi disk melalui subsistem independen (*Disk Manager & Buffer Pool Manager*).
3. Halaman (*Page*) adalah unit granularitas disk I/O fundamental (umumnya 4KB-16KB). Di dalam halaman, arsitektur **Slotted-Page** memecah koordinat menjadi *Header*, *Slot Indirection Vector*, *Free Space*, dan *Tuple Storage*.
4. Indirection Slot Array bertindak sebagai abstraksi penunjuk; RID `(PageID, SlotID)` bersifat stabil kendati tuple fisik bergeser di dalam halaman saat proses defragmentasi dan kompaksi memori dilakukan.
5. Tuple fisik mengemas data secara padat melalui *Tuple Header*, *Null Bitmap*, penyelarasan memori (*padding*), serta offset terpisah untuk tipe data dinamis (*variable-length*).

---

## SEKSI 17 — GLOSARIUM

* **Buffer Pool**: Blok memori RAM teralokasi yang berfungsi menampung cache halaman disk yang sedang aktif dibaca atau dimodifikasi oleh DBMS.
* **Defragmentasi/Kompaksi**: Proses realokasi memori internal di dalam halaman untuk menyatukan ruang-ruang kosong yang terpecah menjadi satu kesatuan ruang kontigu.
* **Free Space Pointer**: Penunjuk biner (*byte offset*) pada header halaman yang menandai batas akhir terendah di mana data tuple baru dapat ditulis.
* **Indirection Layer**: Lapisan pointer perantara yang memisahkan pengenal logis (RID) dari lokasi fisik memori (*byte offset*).
* **Null Bitmap**: Vektor bit individual yang digunakan untuk mencatat status null suatu kolom tanpa mengorbankan alokasi ruang tipe data aslinya.
* **Page (Halaman)**: Satuan blok biner berukuran tetap yang menjadi acuan dasar transaksi I/O antara disk dan memori utama.
* **Record Identifier (RID/TID)**: Tanda pengenal global deterministik dari sebuah baris basis data, umumnya gabungan dari Page Identifier dan Slot Index.
* **Slotted Page**: Format organisasi halaman di mana slot array tumbuh searah offset positif, dan data baris tumbuh dari ujung akhir ke arah offset negatif.
* **Tombstone**: Penanda biner khusus pada slot rekaman yang menunjukkan bahwa baris telah dihapus secara logis dan siap direklamasi.
* **Torn Write**: Fenomena korupsi data di mana sistem mati mendadak saat baru menuliskan sebagian sektor dari satu halaman penuh ke dalam media penyimpanan fisik.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi**:
  * Mahasiswa sering kali bingung membedakan antara *Block* pada perangkat keras, *Cluster* pada File System OS, dan *Page* pada DBMS. Tegaskan bahwa DBMS Page adalah konstruksi logis software database, meskipun ukurannya diupayakan selaras dengan sektor hardware untuk efisiensi transfer bus.
  * Tunjukkan secara visual di papan tulis mengapa pointer `Slot ID` tidak boleh diubah nilainya saat ada baris di tengah yang dihapus: tunjukkan bahwa indeks pohon B+ Tree di luar halaman akan menunjuk ke baris yang salah jika `Slot ID` digeser.
* **Jebakan Pedagogis (Pedagogical Pitfalls)**:
  * Hindari mengajarkan manipulasi basis data langsung menggunakan operasi SQL pada awal bab arsitektur ini. Fokuskan instruksi pada manipulasi array byte dan serialisasi C-struct/Python-struct agar peserta memiliki intuisi mekanikal sistem level rendah.
* **Diferensiasi Pembelajaran**:
  * Bagi siswa pemula: Fokuskan pemahaman pada cara kerja *Slotted Page* dan perhitungan kalkulasi ruang bebas manual.
  * Bagi siswa tingkat lanjut: Tantang mereka untuk mengimplementasikan *Lock-Free Slotted Page* menggunakan operasi primitif atomik CPU (`Compare-And-Swap`).

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal Rilis | Penulis / Kontributor | Perubahan Signifikan |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | 15 Oktober 2023 | Core Architecture Curriculum Team | Rilis inisial modul arsitektur storage engine dan slotted-page layout. |
| **v1.1.0** | 22 Januari 2024 | System Performance Special Interest Group | Penambahan materi Null Bitmap, mitigasi torn write, dan kode praktis defragmentasi memori. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* ⬅️ **Modul Sebelumnya**: `CS-FND-06-03` (Algoritma Graph Terdistribusi & Optimasi Jaringan)
* ➡️ **Modul Berikutnya**: `CS-FND-07-02` (Buffer Pool Management: Pola Eviksi LRU-K, Clock Sweep, dan Dirty Page Flushing)
* 📋 **Indeks Kategori**: `01-Core-Foundations / 07-Basis-Data-&-Sistem-Penyimpanan`