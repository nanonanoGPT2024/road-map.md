# BAB 01 — Fondasi Sintaks Go, Type System, Memory Allocation (Stack vs Heap), & Pointer Semantics — Quiz & Chapter Challenge

---

## 📝 Bagian 1: Ujian Konsep & Pemahaman Teknis (10 Soal Pilihan Ganda)

---

### Soal 1

Perhatikan kode berikut:

```go
package main

import "fmt"

func modify(val int) {
    val = 100
}

func main() {
    x := 42
    modify(x)
    fmt.Println(x)
}
```

Apa output dari program ini dan mengapa?

**A.** `100` — karena fungsi `modify` mengubah nilai `x` secara langsung melalui stack frame yang sama.

**B.** `42` — karena Go menggunakan *pass-by-value*, sehingga `modify` menerima salinan dari `x`, bukan referensinya.

**C.** `0` — karena variabel integer di Go diinisialisasi ulang ke zero value saat masuk ke fungsi baru.

**D.** Compile error — karena Go tidak mengizinkan assignment ulang terhadap parameter fungsi.

---

**✅ Kunci Jawaban: B**

**Penjelasan Mendalam:**

Go secara fundamental menggunakan mekanisme **pass-by-value** untuk semua tipe data primitif. Ketika `modify(x)` dipanggil, Go membuat **salinan independen** dari nilai `x` (yaitu `42`) dan menempatkannya di stack frame milik fungsi `modify`. Variabel `val` di dalam `modify` adalah entitas memori yang sepenuhnya terpisah dari `x` di `main`.

Ketika `val = 100` dieksekusi, hanya salinan lokal tersebut yang berubah. Setelah fungsi `modify` selesai dan stack frame-nya di-pop, perubahan tersebut hilang sepenuhnya. Variabel `x` di `main` tetap berada di stack frame `main` dengan nilai `42` dan tidak pernah tersentuh.

**Mengapa pilihan lain salah:**
- **A salah:** Stack frame `modify` dan `main` adalah region memori yang **berbeda dan terisolasi**. Setiap fungsi memiliki stack frame sendiri; tidak ada sharing memori antar frame untuk variabel lokal.
- **C salah:** Go memang memiliki konsep zero value (integer → `0`), tetapi zero value hanya berlaku saat **deklarasi variabel baru**, bukan saat nilai di-pass ke fungsi.
- **D salah:** Go **mengizinkan** re-assignment terhadap parameter fungsi. Parameter fungsi diperlakukan sebagai variabel lokal biasa di dalam scope fungsi tersebut.

---

### Soal 2

Perhatikan kode berikut:

```go
package main

import "fmt"

func escape() *int {
    x := 99
    return &x
}

func main() {
    ptr := escape()
    fmt.Println(*ptr)
}
```

Di mana variabel `x` di dalam fungsi `escape()` dialokasikan, dan mengapa?

**A.** Di **stack** — karena `x` adalah variabel lokal bertipe `int` yang ukurannya diketahui saat compile time.

**B.** Di **heap** — karena alamat `x` dikembalikan ke luar scope fungsi, sehingga Go's escape analysis mendeteksi bahwa `x` harus bertahan lebih lama dari stack frame-nya.

**C.** Di **stack** — karena Go menggunakan *garbage collector* yang akan menjaga nilai `x` tetap valid meskipun stack frame sudah di-pop.

**D.** Di **heap** — karena semua variabel yang menggunakan operator `&` selalu dialokasikan di heap secara default oleh Go runtime.

---

**✅ Kunci Jawaban: B**

**Penjelasan Mendalam:**

Ini adalah contoh klasik dari **heap escape** yang dideteksi oleh **escape analysis** compiler Go. Proses ini terjadi pada fase kompilasi (`go build`), bukan saat runtime.

Secara normal, `x` sebagai variabel lokal bertipe `int` akan dialokasikan di stack frame fungsi `escape()`. Namun, karena `&x` (alamat memori `x`) dikembalikan sebagai return value dan akan digunakan di luar scope `escape()`, compiler menyadari bahwa jika `x` tetap di stack, maka ketika stack frame `escape()` di-pop setelah fungsi selesai, pointer `ptr` di `main` akan menunjuk ke memori yang sudah tidak valid (*dangling pointer*).

Untuk mencegah hal ini, compiler Go secara otomatis **memindahkan alokasi `x` ke heap**. Heap memiliki lifetime yang dikelola oleh garbage collector, sehingga `x` tetap valid selama masih ada pointer yang mereferensikannya. Anda dapat memverifikasi ini dengan perintah:

```bash
go build -gcflags="-m" main.go
# Output: ./main.go:6:2: moved to heap: x
```

**Mengapa pilihan lain salah:**
- **A salah:** Meskipun `int` berukuran tetap dan *eligible* untuk stack allocation, faktor penentu bukan hanya ukuran tipe data, tetapi **apakah lifetime-nya melampaui scope fungsi**. Karena alamatnya di-return, ia harus di-heap.
- **C salah:** Garbage collector **tidak bekerja pada stack**. GC hanya mengelola memori di heap. Stack frame di-pop secara deterministik saat fungsi return, terlepas dari GC.
- **D salah:** Penggunaan `&` **tidak selalu** menyebabkan heap allocation. Jika pointer hanya digunakan di dalam scope yang sama atau scope yang lebih dalam (tidak melarikan diri ke luar), escape analysis dapat membuktikan bahwa alokasi stack masih aman.

---

### Soal 3

Perhatikan kode berikut:

```go
package main

import "fmt"

type Config struct {
    MaxConn int
    Timeout float64
    Name    string
}

func updateConfig(c Config) {
    c.MaxConn = 500
    c.Name = "updated"
}

func main() {
    cfg := Config{MaxConn: 100, Timeout: 30.5, Name: "original"}
    updateConfig(cfg)
    fmt.Println(cfg.MaxConn, cfg.Name)
}
```

Apa output yang benar?

**A.** `500 updated` — karena struct di Go di-pass by reference secara default.

**B.** `100 original` — karena struct di Go di-pass by value, sehingga `updateConfig` bekerja pada salinan struct.

**C.** `500 original` — karena field integer di-pass by reference sedangkan string di-pass by value.

**D.** Compile error — karena struct tidak dapat di-pass langsung ke fungsi tanpa menggunakan pointer.

---

**✅ Kunci Jawaban: B**

**Penjelasan Mendalam:**

Di Go, **struct adalah value type**. Ini berarti ketika sebuah struct di-pass ke fungsi, **seluruh isi struct disalin** ke stack frame fungsi penerima. Tidak ada field yang di-pass secara selektif by reference.

Dalam kasus ini, `updateConfig(cfg)` membuat salinan lengkap dari struct `Config` — semua field (`MaxConn`, `Timeout`, `Name`) disalin ke variabel `c` yang merupakan entitas terpisah. Modifikasi `c.MaxConn = 500` dan `c.Name = "updated"` hanya berdampak pada salinan lokal tersebut. Struct `cfg` di `main` tidak terpengaruh sama sekali.

Ini memiliki implikasi performa: untuk struct yang besar, pass-by-value bisa mahal karena overhead penyalinan memori. Dalam skenario seperti ini, idiom Go yang tepat adalah menggunakan pointer receiver:

```go
func updateConfig(c *Config) {
    c.MaxConn = 500  // Memodifikasi struct asli
    c.Name = "updated"
}
// Dipanggil dengan: updateConfig(&cfg)
```

**Mengapa pilihan lain salah:**
- **A salah:** Go **tidak** memiliki mekanisme pass-by-reference implisit untuk struct. Berbeda dengan bahasa seperti Python atau JavaScript yang menggunakan reference semantics untuk objek, Go secara eksplisit memisahkan value semantics dan pointer semantics.
- **C salah:** Go tidak membedakan mekanisme passing berdasarkan tipe field di dalam struct. Seluruh struct disalin sebagai satu unit memori.
- **D salah:** Go **mengizinkan** passing struct by value. Bahkan, ini adalah default behavior. Penggunaan pointer adalah pilihan desain, bukan keharusan sintaksis.

---

### Soal 4

Perhatikan kode berikut:

```go
package main

import "fmt"

func main() {
    var a *int
    fmt.Println(a)
    fmt.Println(*a)
}
```

Apa yang terjadi saat program ini dijalankan?

**A.** Output: `<nil>` lalu `0` — karena dereferencing nil pointer mengembalikan zero value dari tipe yang ditunjuk.

**B.** Output: `<nil>` lalu program **panic: runtime error: invalid memory address or nil pointer dereference**.

**C.** Compile error — karena Go mendeteksi nil pointer dereference pada saat kompilasi.

**D.** Output: `0x0` lalu `0` — karena Go secara otomatis mengalokasikan memori saat pointer di-dereference.

---

**✅ Kunci Jawaban: B**

**Penjelasan Mendalam:**

`var a *int` mendeklarasikan pointer ke `int` tanpa inisialisasi. Sesuai dengan aturan zero value Go, pointer yang tidak diinisialisasi memiliki nilai `nil` (setara dengan alamat `0x0` atau null pointer di bahasa lain).

`fmt.Println(a)` mencetak `<nil>` dengan sukses karena hanya membaca **nilai pointer itu sendiri** (yaitu `nil`), bukan nilai yang ditunjuknya.

`fmt.Println(*a)` adalah operasi **nil pointer dereference** — mencoba membaca nilai pada alamat memori `0x0`. Alamat ini tidak pernah di-map ke memori proses yang valid (OS sengaja membuat halaman pertama memori tidak dapat diakses sebagai mekanisme proteksi). Akibatnya, Go runtime menangkap **segmentation fault** dan mengubahnya menjadi **panic** dengan pesan yang informatif.

Panic ini **tidak dapat di-recover secara parsial** untuk melanjutkan eksekusi normal tanpa penanganan eksplisit menggunakan `recover()` dalam `defer`.

**Mengapa pilihan lain salah:**
- **A salah:** Go **tidak** secara otomatis mengembalikan zero value saat nil pointer di-dereference. Ini adalah keputusan desain yang disengaja untuk mencegah bug yang tersembunyi (berbeda dengan beberapa bahasa yang memiliki null-safe dereference).
- **C salah:** Go compiler umumnya **tidak dapat** mendeteksi nil pointer dereference pada compile time kecuali dalam kasus yang sangat trivial. Ini adalah **runtime error**, bukan compile error. Static analysis tools seperti `staticcheck` dapat membantu mendeteksi beberapa kasus.
- **D salah:** Go **tidak** melakukan lazy allocation saat pointer di-dereference. Tidak ada mekanisme semacam itu di Go runtime. Programmer bertanggung jawab penuh untuk memastikan pointer valid sebelum di-dereference.

---

### Soal 5

Perhatikan kode berikut:

```go
package main

import "fmt"

func main() {
    s1 := []int{1, 2, 3}
    s2 := s1
    s2[0] = 99

    fmt.Println(s1[0])
    fmt.Println(s2[0])
}
```

Apa output dari program ini?

**A.** `1` dan `99` — karena `s2 := s1` membuat salinan slice yang independen.

**B.** `99` dan `99` — karena slice adalah reference type; `s1` dan `s2` berbagi underlying array yang sama.

**C.** `99` dan `1` — karena assignment slice membalik urutan elemen.

**D.** Compile error — karena slice tidak dapat di-assign langsung ke variabel baru tanpa menggunakan `copy()`.

---

**✅ Kunci Jawaban: B**

**Penjelasan Mendalam:**

Ini adalah salah satu konsep paling krusial dalam Go: **slice adalah reference type**. Sebuah slice di Go bukanlah array itu sendiri, melainkan sebuah **slice header** yang terdiri dari tiga komponen:

```
┌─────────────────────────────────────────┐
│  Slice Header (24 bytes pada 64-bit)    │
│  ┌──────────┬──────────┬──────────────┐ │
│  │ ptr      │ len      │ cap          │ │
│  │ *[0]int  │ int      │ int          │ │
│  └──────────┴──────────┴──────────────┘ │
└─────────────────────────────────────────┘
        │
        ▼
   [1, 2, 3]  ← Underlying Array (di heap)
```

Ketika `s2 := s1` dieksekusi, Go menyalin **slice header** (pointer, len, cap), bukan underlying array. Akibatnya, `s1` dan `s2` memiliki field `ptr` yang menunjuk ke **underlying array yang sama** di heap.

Ketika `s2[0] = 99` dieksekusi, perubahan dilakukan pada underlying array tersebut. Karena `s1` juga menunjuk ke array yang sama, `s1[0]` juga menjadi `99`.

Untuk membuat salinan yang benar-benar independen, gunakan built-in `copy()`:

```go
s2 := make([]int, len(s1))
copy(s2, s1)
s2[0] = 99
// Sekarang s1[0] tetap 1
```

**Mengapa pilihan lain salah:**
- **A salah:** `s2 := s1` **tidak** membuat deep copy dari slice. Ini hanya menyalin slice header. Untuk deep copy, diperlukan `copy()` atau membuat slice baru secara manual.
- **C salah:** Assignment slice tidak memiliki efek samping berupa pembalikan elemen. Ini tidak ada dalam spesifikasi Go.
- **D salah:** Go **mengizinkan** assignment slice secara langsung. Ini adalah operasi yang valid dan sering digunakan, meskipun programmer harus memahami implikasi shared underlying array-nya.

---

### Soal 6

Perhatikan kode berikut:

```go
package main

import "fmt"

func main() {
    var x interface{
