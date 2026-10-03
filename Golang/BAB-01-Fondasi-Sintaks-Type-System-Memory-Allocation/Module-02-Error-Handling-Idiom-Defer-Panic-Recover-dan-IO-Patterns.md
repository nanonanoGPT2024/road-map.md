# Idiomatic Error Handling, Defer Stack Execution, Panic/Recover Guard, & Standard IO Patterns

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

- **Membangun** sistem error handling yang idiomatic menggunakan `error` interface, sentinel errors, dan custom error types tanpa bergantung pada exception-based patterns
- **Mendiagnosis** urutan eksekusi `defer` stack dan memprediksi output program secara akurat dalam skenario nested defer, panic, dan return values
- **Mengimplementasikan** guard pattern menggunakan `panic`/`recover` untuk memisahkan program logic errors dari recoverable runtime errors
- **Merancang** pipeline Standard IO yang efisien menggunakan `bufio`, `fmt`, `os`, dan `io` packages untuk operasi baca-tulis production-grade
- **Membedakan** kapan menggunakan `errors.Is`, `errors.As`, `fmt.Errorf` dengan `%w`, dan custom error types dalam konteks arsitektur layered
- **Menulis** kode yang memenuhi standar Go idiom sehingga lolos code review di tim engineering level senior

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah memahami:

| Konsep | Relevansi |
|---|---|
| **Go interface mechanics** | `error` adalah interface; Anda harus paham duck typing dan implicit implementation |
| **Function return values** | Go mengembalikan multiple values; error selalu sebagai return value terakhir |
| **Stack vs Heap allocation** | Defer frame dialokasikan di heap; memahami ini krusial untuk performance analysis |
| **Goroutine & call stack** | Panic propagates up the call stack; perlu paham konsep stack frame |
| **Pointer semantics** | Custom error types sering menggunakan pointer receivers |
| **Struct dan method** | Diperlukan untuk membuat custom error types |
| **Variadic functions** | `fmt.Fprintf`, `fmt.Sscanf` menggunakan variadic arguments |

---

## 3. Concept

### 3.1 Filosofi Error Handling di Go

Go secara sadar **menolak** model exception yang digunakan Java, Python, dan C++. Keputusan desain ini bukan keterbatasan — ini adalah filosofi eksplisit yang lahir dari pengalaman membangun sistem skala besar di Google.

Dalam model exception:
```
// Pseudocode model exception (BUKAN Go)
try {
    result = riskyOperation()
} catch (IOException e) {
    // Error tersembunyi di jalur alternatif
}
```

Masalah fundamental model exception:
1. **Hidden control flow**: Exception dapat loncat melewati banyak stack frame tanpa terlihat di signature fungsi
2. **Unchecked exceptions**: Compiler tidak memaksa Anda menangani error tertentu
3. **Performance overhead**: Stack unwinding pada exception path sangat mahal
4. **Readability**: Sulit membaca kode dan mengetahui error apa yang mungkin muncul

Go memilih pendekatan berbeda: **errors are values**. Error adalah nilai biasa yang dikembalikan seperti nilai lain, diperiksa secara eksplisit, dan dapat dimanipulasi dengan tools standar.

### 3.2 Error Interface — Pondasi Sistem

```go
// Definisi dari package builtin
type error interface {
    Error() string
}
```

Ini adalah interface paling sederhana di Go — hanya satu method. Kesederhanaan ini adalah kekuatan: **semua tipe yang memiliki method `Error() string` adalah error**. Tidak ada inheritance, tidak ada class hierarchy.

### 3.3 Defer — Deferred Execution Mechanism

`defer` adalah statement yang menunda eksekusi sebuah fungsi hingga surrounding function selesai (baik normal return maupun panic). Defer statements dieksekusi dalam urutan **LIFO (Last In, First Out)** — seperti stack.

Tiga properti krusial defer yang sering disalahpahami:

**Properti 1: Arguments dievaluasi saat defer statement dieksekusi, bukan saat deferred function dipanggil**

```go
func example() {
    x := 10
    defer fmt.Println(x) // x=10 dievaluasi SEKARANG
    x = 20
    // Output: 10, bukan 20
}
```

**Properti 2: Deferred functions dapat membaca dan memodifikasi named return values**

```go
func double(x int) (result int) {
    defer func() {
        result *= 2 // Memodifikasi named return value
    }()
    result = x
    return // result = x, lalu defer mengubahnya menjadi x*2
}
```

**Properti 3: Defer dieksekusi bahkan ketika panic terjadi**

Ini adalah properti yang membuat defer menjadi mekanisme cleanup yang sempurna.

### 3.4 Panic dan Recover — Guard Mechanism

`panic` adalah mekanisme untuk menghentikan eksekusi normal ketika terjadi kondisi yang **tidak dapat dipulihkan secara logis** — bukan untuk error handling rutin.

`recover` adalah built-in function yang dapat menghentikan propagasi panic dan mengembalikan nilai yang di-pass ke `panic()`. `recover` hanya efektif ketika dipanggil di dalam deferred function.

### 3.5 Standard IO Patterns

Go menyediakan ekosistem IO yang kaya melalui beberapa package:
- `fmt`: Formatted I/O (print, scan, sprintf)
- `os`: File operations, stdin/stdout/stderr
- `bufio`: Buffered I/O untuk efisiensi
- `io`: Core I/O interfaces (`Reader`, `Writer`, `Closer`)
- `io/ioutil` (deprecated) → `os` dan `io` di Go 1.16+

---

## 4. Why?

### Mengapa Error Handling Eksplisit?

**Masalah yang dipecahkan**: Dalam sistem distributed seperti microservices Tokopedia, sebuah request payment bisa melewati 15+ service calls. Jika error handling tidak eksplisit, debugging menjadi mimpi buruk.

```
Request → Auth Service → User Service → Payment Service → Bank API
                                              ↓
                                    Mana yang gagal?
                                    Kenapa gagal?
                                    Apakah perlu retry?
                                    Apakah transaksi sudah terjadi?
```

Error sebagai nilai memaksa developer untuk **secara eksplisit memutuskan** apa yang terjadi pada setiap titik kegagalan. Ini menghasilkan kode yang lebih robust dan sistem yang lebih dapat diprediksi.

### Mengapa Defer?

**Masalah yang dipecahkan**: Resource leak adalah salah satu bug paling berbahaya di sistem production.

```go
// Tanpa defer — resource leak jika terjadi early return
func processFile(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    
    data, err := readData(f)
    if err != nil {
        f.Close() // Harus ingat close di SETIAP early return
        return err
    }
    
    result, err := processData(data)
    if err != nil {
        f.Close() // Harus ingat close lagi
        return err
    }
    
    f.Close() // Dan di sini
    return nil
}
```

Dengan defer, cleanup terjamin:
```go
func processFile(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    defer f.Close() // Satu baris, dijamin berjalan
    
    // ... rest of logic
}
```

### Mengapa Panic/Recover?

**Masalah yang dipecahkan**: Membedakan antara "error yang bisa ditangani" vs "kondisi program yang tidak valid".

- **Error yang bisa ditangani**: File tidak ditemukan, network timeout, invalid input → gunakan `error` return
- **Kondisi program tidak valid**: Index out of bounds, nil pointer dereference, invariant violation → bisa menggunakan panic

Recover memungkinkan boundary (seperti HTTP handler, goroutine launcher) untuk mencegah satu goroutine yang crash merobohkan seluruh server.

### Mengapa Buffered IO?

**Masalah yang dipecahkan**: Unbuffered IO melakukan syscall untuk setiap operasi baca/tulis, yang sangat mahal.

```
Unbuffered: 1000 writes = 1000 syscalls = sangat lambat
Buffered:   1000 writes = ~10 syscalls (buffer 4KB) = jauh lebih cepat
```

---

## 5. What?

### 5.1 Definisi Presisi: Error

**`error`** adalah built-in interface type dengan satu method `Error() string`. Nilai `nil` dari tipe error berarti "tidak ada error". Nilai non-nil berarti terjadi kesalahan.

**Sentinel Error**: Variabel error yang di-export dan dapat dibandingkan dengan `==` atau `errors.Is`.
```go
var ErrNotFound = errors.New("not found")
```

**Error Wrapping**: Mekanisme untuk membungkus error dengan konteks tambahan sambil mempertahankan error asli untuk inspeksi.
```go
fmt.Errorf("failed to open config: %w", err)
```

**`errors.Is(err, target)`**: Memeriksa apakah `err` (atau error yang di-wrap di dalamnya) sama dengan `target`. Menggunakan method `Is(error) bool` jika ada, atau `==` sebagai fallback.

**`errors.As(err, target)`**: Memeriksa apakah `err` (atau error yang di-wrap) dapat di-assign ke tipe yang ditunjuk `target`. Menggunakan method `As(interface{}) bool` jika ada.

### 5.2 Definisi Presisi: Defer

**`defer`** adalah keyword yang menunda eksekusi sebuah function call hingga surrounding function returns. Deferred calls dieksekusi dalam urutan LIFO. Defer stack adalah bagian dari goroutine's runtime state.

**Spesifikasi teknis**:
- Argumen dievaluasi **immediately** saat defer statement dieksekusi
- Deferred function dipanggil **setelah** return expression dievaluasi
- Deferred function dapat memodifikasi **named return values**
- Defer berjalan bahkan saat panic terjadi

### 5.3 Definisi Presisi: Panic & Recover

**`panic(v interface{})`**: Built-in function yang menghentikan eksekusi normal goroutine saat ini. Panic menyebabkan stack unwinding — deferred functions berjalan, lalu panic propagates ke caller, terus sampai ke goroutine's top-level function, yang kemudian crash dengan stack trace.

**`recover() interface{}`**: Built-in function yang menghentikan panic propagation dan mengembalikan nilai yang di-pass ke `panic()`. Hanya efektif jika dipanggil **langsung** di dalam deferred function. Jika tidak ada panic yang aktif, `recover()` mengembalikan `nil`.

### 5.4 Definisi Presisi: Standard IO

**`io.Reader`**: Interface dengan method `Read(p []byte) (n int, err error)`.
**`io.Writer`**: Interface dengan method `Write(p []byte) (n int, err error)`.
**`bufio.Scanner`**: Membaca input line-by-line dengan buffering otomatis.
**`bufio.Writer`**: Wraps `io.Writer` dengan buffer untuk mengurangi syscalls.
**`fmt.Fprintf(w io.Writer, format string, a ...interface{})`**: Menulis formatted output ke `w`.

---

## 6. How?

### 6.1 Mekanisme Error Handling — Step by Step

**Step 1: Error Creation**
```
errors.New("message")
    ↓
Mengalokasikan struct errorString{s: "message"} di heap
    ↓
Mengembalikan pointer *errorString yang implement interface error
```

**Step 2: Error Propagation dengan Wrapping**
```
fmt.Errorf("context: %w", originalErr)
    ↓
Mengalokasikan struct wrapError{msg: "context: original", err: originalErr}
    ↓
Chain: wrapError → originalErr
```

**Step 3: Error Inspection**
```
errors.Is(err, target)
    ↓
Cek: err == target? → Ya: return true
    ↓ Tidak
Cek: err memiliki method Is(error) bool? → Panggil err.Is(target)
    ↓ Tidak
Cek: err memiliki method Unwrap() error? → err = err.Unwrap(), ulang
    ↓ Tidak ada Unwrap
return false
```

### 6.2 Mekanisme Defer Stack — Step by Step

```
func main() {
    defer A()    // Push A ke defer stack
    defer B()    // Push B ke defer stack  
    defer C()    // Push C ke defer stack
    return
}

Defer Stack (LIFO):
┌─────────────────┐
│      C()        │ ← Top (dieksekusi pertama)
├─────────────────┤
│      B()        │
├─────────────────┤
│      A()        │ ← Bottom (dieksekusi terakhir)
└─────────────────┘

Urutan eksekusi: C → B → A
```

**Argument Evaluation Timeline**:
```
x := 10
defer fmt.Println(x)  ← x=10 di-capture SEKARANG (saat statement ini dieksekusi)
x = 20
return
// Output: 10

vs.

x := 10
defer func() {
    fmt.Println(x)    ← x dibaca SAAT defer function dieksekusi (closure)
}()
x = 20
return
// Output: 20
```

### 6.3 Mekanisme Panic/Recover — Step by Step

```
goroutine G1:
    func A() {
        defer func() {
            if r := recover(); r != nil {  // Step 5: recover() dipanggil
                fmt.Println("Recovered:", r) // Step 6: panic dihentikan
            }
        }()
        B()  // Step 1: panggil B
    }
    
    func B() {
        C()  // Step 2: panggil C
    }
    
    func C() {
        panic("something went wrong")  // Step 3: panic dipicu
        // Step 4: stack unwind dimulai
        //   - C's deferred functions run (tidak ada)
        //   - B's deferred functions run (tidak ada)
        //   - A's deferred functions run → recover() dipanggil
    }
```

**Panic Propagation Flow**:
```
panic("error")
    ↓
Runtime menandai goroutine sebagai "panicking"
    ↓
Eksekusi deferred functions di current frame (LIFO)
    ↓
Jika recover() dipanggil di salah satu deferred function:
    → Panic dihentikan
    → Goroutine melanjutkan eksekusi normal setelah deferred function
