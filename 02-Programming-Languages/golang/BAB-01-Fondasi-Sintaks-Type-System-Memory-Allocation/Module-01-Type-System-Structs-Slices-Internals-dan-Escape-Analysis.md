# Go Type System, Struct Layout, Slice Header Anatomy, & Compiler Escape Analysis

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

1. **Menjelaskan** perbedaan fundamental antara value types dan reference types dalam Go beserta implikasi memory-nya
2. **Menganalisis** layout memori sebuah struct menggunakan `unsafe.Sizeof`, `unsafe.Alignof`, dan `unsafe.Offsetof` untuk mendiagnosis padding waste
3. **Mendeskripsikan** anatomi internal slice header (pointer, length, capacity) dan memprediksi perilaku sharing/copying antar slice
4. **Menginterpretasikan** output `go build -gcflags="-m"` untuk menentukan apakah sebuah variabel dialokasikan di stack atau heap
5. **Menulis ulang** struct dan fungsi untuk mengurangi heap allocation berdasarkan hasil escape analysis
6. **Membangun** sistem cache sederhana yang memory-efficient dengan mempertimbangkan struct alignment dan zero-copy slice operations

---

## 2. Prerequisite

Sebelum melanjutkan, pastikan Anda telah memahami:

| Konsep | Tingkat Pemahaman yang Dibutuhkan |
|--------|-----------------------------------|
| Sintaks dasar Go (variabel, fungsi, loop) | Mahir — bisa menulis program sederhana tanpa referensi |
| Konsep pointer dasar (`*T`, `&x`) | Dasar — tahu cara membuat dan dereference pointer |
| Stack vs Heap (konseptual) | Dasar — tahu bahwa stack lebih cepat dari heap |
| Cara menjalankan `go build` dan `go run` | Mahir — familiar dengan Go toolchain |
| Array vs Slice di Go (perbedaan sintaks) | Dasar — tahu `[5]int` berbeda dengan `[]int` |

---

## 3. Concept

### 3.1 Fondasi: Bagaimana Go Memodelkan Data

Go dirancang dengan filosofi bahwa **programmer harus bisa memprediksi perilaku memori** tanpa harus menjadi ahli garbage collector. Berbeda dengan Java yang menyembunyikan semua detail memori, atau C yang mengekspos terlalu banyak, Go menemukan titik tengah: Anda dapat *memahami* apa yang terjadi di memori tanpa harus *mengelolanya secara manual*.

Sistem tipe Go dibangun di atas tiga pilar:

**Pilar 1: Setiap tipe memiliki ukuran dan alignment yang deterministik**
Tidak ada kejutan. `int64` selalu 8 byte. `bool` selalu 1 byte. Ini berbeda dengan C di mana `int` bisa 2, 4, atau 8 byte tergantung platform.

**Pilar 2: Value semantics adalah default**
Ketika Anda assign atau pass sebuah nilai, Go *menyalin* nilainya. Ini mencegah aliasing bugs yang umum di bahasa lain.

**Pilar 3: Compiler, bukan programmer, yang memutuskan stack vs heap**
Anda tidak bisa memaksa sebuah variabel ada di stack (seperti `alloca` di C). Compiler Go menggunakan *escape analysis* untuk memutuskan secara otomatis — tetapi Anda bisa *mempengaruhi* keputusannya dengan cara menulis kode.

### 3.2 Go Type System: Kategori Tipe

Go membagi tipe menjadi beberapa kategori dengan karakteristik memori yang berbeda:

```
┌─────────────────────────────────────────────────────────┐
│                    GO TYPE SYSTEM                        │
├─────────────────────┬───────────────────────────────────┤
│   BASIC TYPES       │   COMPOSITE TYPES                  │
│                     │                                    │
│   bool (1B)         │   Array    [N]T  (value)           │
│   int8..int64       │   Struct   struct{} (value)        │
│   uint8..uint64     │   Slice    []T  (reference-like)   │
│   float32/64        │   Map      map[K]V (reference)     │
│   complex64/128     │   Channel  chan T (reference)      │
│   string (16B)      │   Pointer  *T (reference)          │
│   byte = uint8      │   Function func(...) (reference)   │
│   rune = int32      │   Interface interface{} (16B)      │
└─────────────────────┴───────────────────────────────────┘
```

**Perbedaan kritis "value" vs "reference-like":**

- **Value types**: Saat di-assign atau di-pass ke fungsi, *seluruh data* disalin. Struct `{x, y, z int}` yang di-pass ke fungsi akan menyalin 24 byte.
- **Reference-like types**: Saat di-assign atau di-pass, hanya *header* yang disalin. Slice `[]int` dengan 1 juta elemen tetap hanya menyalin 24 byte (header).

> **Catatan penting**: Go tidak memiliki "reference types" dalam artian Java. Slice, map, channel adalah *nilai yang mengandung pointer* di dalamnya. Ini perbedaan yang sangat fundamental.

### 3.3 Struct Layout dan Memory Padding

CPU modern tidak bisa membaca data dari alamat sembarang. Sebuah `int64` harus berada di alamat yang kelipatan 8. Sebuah `int32` harus di kelipatan 4. Ini disebut **alignment requirement**.

Ketika Go menyusun field-field dalam sebuah struct, compiler akan menambahkan **padding bytes** agar setiap field berada di alamat yang sesuai alignment-nya.

```go
// Struct dengan layout BURUK (banyak padding)
type BadLayout struct {
    a bool    // 1 byte  + 7 byte padding
    b int64   // 8 byte
    c bool    // 1 byte  + 7 byte padding
    d int64   // 8 byte
}
// Total: 32 byte (16 byte data + 16 byte padding = 50% waste!)

// Struct dengan layout BAIK (padding minimal)
type GoodLayout struct {
    b int64   // 8 byte
    d int64   // 8 byte
    a bool    // 1 byte
    c bool    // 1 byte  + 6 byte padding (struct alignment)
}
// Total: 18 byte → padded to 24 byte (hanya 6 byte padding)
```

**Aturan alignment Go:**
- Alignment sebuah field = `unsafe.Alignof(field)` (biasanya = ukuran tipe, max 8)
- Setiap field dimulai di offset yang merupakan kelipatan dari alignment-nya
- Ukuran total struct dibulatkan ke kelipatan alignment field terbesar

### 3.4 Slice Header Anatomy

Ini adalah salah satu konsep paling penting dalam Go. Sebuah slice **bukan** array. Slice adalah *view* ke dalam array yang underlie-nya.

Secara internal, setiap slice adalah sebuah struct dengan tiga field:

```go
// Representasi internal slice (dari runtime/slice.go)
type SliceHeader struct {
    Data uintptr // Pointer ke backing array
    Len  int     // Jumlah elemen yang dapat diakses
    Cap  int     // Total kapasitas backing array dari posisi Data
}
```

Ukuran: `unsafe.Sizeof([]int{})` = **24 byte** di 64-bit system (3 × 8 byte).

### 3.5 Compiler Escape Analysis

Escape analysis adalah proses di mana Go compiler menganalisis *apakah sebuah variabel bisa "kabur" keluar dari scope-nya*. Jika ya, variabel tersebut harus dialokasikan di heap (karena stack frame-nya akan hilang). Jika tidak, bisa tetap di stack.

**Variabel "kabur" ke heap ketika:**
1. Alamatnya dikembalikan dari fungsi (`return &x`)
2. Disimpan dalam interface (`var i interface{} = x`)
3. Dikirim ke goroutine
4. Terlalu besar untuk stack
5. Ukurannya tidak diketahui saat compile time

---

## 4. Why?

### Mengapa Ini Penting di Production?

**Masalah 1: Unexplained Memory Bloat**

Bayangkan Anda memiliki service yang menyimpan 10 juta record user. Struct yang tidak optimal bisa menyebabkan pemborosan memori yang signifikan:

```
BadLayout  × 10,000,000 = 320 MB
GoodLayout × 10,000,000 = 240 MB
Selisih: 80 MB per instance!
```

Jika service Anda berjalan di 50 pod Kubernetes, itu **4 GB RAM terbuang** hanya karena urutan field yang salah.

**Masalah 2: GC Pressure yang Tidak Terduga**

Setiap heap allocation menambah beban pada garbage collector. Service yang mengalokasikan jutaan objek kecil ke heap akan mengalami GC pauses yang sering, meningkatkan latency P99 secara dramatis.

```
Tanpa optimasi: 10,000 req/s → 50,000 heap allocs/s → GC pause setiap 200ms
Dengan optimasi: 10,000 req/s → 5,000 heap allocs/s  → GC pause setiap 2000ms
```

**Masalah 3: Slice Aliasing Bugs**

Tidak memahami slice header menyebabkan bug yang sangat sulit di-debug:

```go
// Bug nyata: modifikasi "salinan" ternyata memodifikasi data asli
original := []int{1, 2, 3, 4, 5}
slice1 := original[:3]  // [1, 2, 3]
slice2 := original[:3]  // [1, 2, 3]
slice1[0] = 999
fmt.Println(slice2[0])  // 999 — BUKAN 1! Ini aliasing bug!
```

**Masalah 4: Performa yang Tidak Konsisten**

Stack allocation jauh lebih cepat dari heap allocation karena:
- Stack: increment/decrement pointer (nanoseconds)
- Heap: malloc + GC tracking overhead (microseconds)

Perbedaan ini terlihat jelas di hot path (kode yang dipanggil jutaan kali per detik).

---

## 5. What?

### 5.1 Definisi Presisi

**Go Type System** adalah seperangkat aturan yang mendefinisikan bagaimana tipe-tipe di Go direpresentasikan di memori, bagaimana operasi pada tipe tersebut berperilaku, dan bagaimana tipe-tipe tersebut berinteraksi satu sama lain.

**Struct Layout** adalah cara compiler Go menyusun field-field sebuah struct di memori, termasuk penambahan padding bytes untuk memenuhi alignment requirements CPU.

**Slice Header** adalah representasi internal sebuah slice value: sebuah struct 24-byte yang berisi pointer ke backing array, length, dan capacity.

**Compiler Escape Analysis** adalah analisis statik yang dilakukan Go compiler untuk menentukan apakah lifetime sebuah variabel terbatas pada stack frame saat ini atau harus diperpanjang dengan alokasi di heap.

### 5.2 Spesifikasi Teknis

#### Ukuran dan Alignment Tipe Dasar (64-bit Linux/macOS/Windows)

| Tipe | Ukuran (byte) | Alignment (byte) |
|------|---------------|------------------|
| `bool` | 1 | 1 |
| `int8`, `uint8`, `byte` | 1 | 1 |
| `int16`, `uint16` | 2 | 2 |
| `int32`, `uint32`, `rune` | 4 | 4 |
| `int64`, `uint64` | 8 | 8 |
| `int`, `uint` | 8 | 8 (platform-dependent) |
| `float32` | 4 | 4 |
| `float64` | 8 | 8 |
| `complex64` | 8 | 4 |
| `complex128` | 16 | 8 |
| `string` | 16 | 8 |
| `[]T` (slice) | 24 | 8 |
| `map[K]V` | 8 | 8 (pointer to runtime.hmap) |
| `chan T` | 8 | 8 (pointer to runtime.hchan) |
| `*T` (pointer) | 8 | 8 |
| `interface{}` | 16 | 8 |
| `func(...)` | 8 | 8 |

#### Aturan Padding

```
Offset field N = smallest multiple of Alignof(field N) ≥ Offset(field N-1) + Sizeof(field N-1)
Sizeof(struct) = smallest multiple of max(Alignof(all fields)) ≥ Offset(last field) + Sizeof(last field)
```

#### Slice Operations dan Efeknya pada Header

| Operasi | Data | Len | Cap | Sharing Backing Array? |
|---------|------|-----|-----|------------------------|
| `s := make([]T, n)` | new alloc | n | n | N/A |
| `s := make([]T, n, m)` | new alloc | n | m | N/A |
| `s2 := s[a:b]` | s.Data + a×sizeof(T) | b-a | s.Cap-a | **Ya** |
| `s2 := append(s, x)` | baru jika Cap penuh | s.Len+1 | baru/lama | **Kondisional** |
| `copy(dst, src)` | dst.Data | min(dst.Len, src.Len) | dst.Cap | **Tidak** |

---

## 6. How?

### 6.1 Mekanisme Struct Layout Step-by-Step

Mari kita trace secara manual bagaimana compiler menyusun struct ini:

```go
type Example struct {
    A bool    // field 0
    B int32   // field 1
    C int64   // field 2
    D bool    // field 3
    E int16   // field 4
}
```

**Step 1: Tentukan alignment setiap field**
- A: bool, align=1
- B: int32, align=4
- C: int64, align=8
- D: bool, align=1
- E: int16, align=2

**Step 2: Hitung offset setiap field**

```
Offset A = 0 (pertama, selalu 0)
           A = 1 byte → posisi berikutnya = 1

Offset B: align=4, posisi saat ini=1
           Butuh kelipatan 4 ≥ 1 → 4
           Padding: 3 byte (offset 1,2,3)
           B = 4 byte → posisi berikutnya = 8

Offset C: align=
