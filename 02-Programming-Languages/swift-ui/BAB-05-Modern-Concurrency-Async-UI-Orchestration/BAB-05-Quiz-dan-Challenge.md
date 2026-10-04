# BAB 05: Quiz, Challenge, & Knowledge Check
**Modern Concurrency & Async UI Orchestration**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Cooperative Thread Pool vs. GCD Thread Explosion
Grand Central Dispatch (GCD) secara historis rentan terhadap masalah *thread explosion* ketika ratusan *concurrent queue* mengalami *blocking*. Jelaskan secara mendalam bagaimana arsitektur *Cooperative Thread Pool* pada Swift Concurrency memecahkan masalah ini. Apa batasan jumlah *thread* yang dialokasikan oleh *runtime* Swift Concurrency, dan bagaimana mekanisme *continuation* memungkinkan penangguhan (*suspension*) eksekusi tanpa memblokir kernel thread yang mendasarinya?

### Soal 1.2: Structured Concurrency vs. Unstructured Tasks
Bandingkan semantik siklus hidup, propagasi pembatalan (*cancellation propagation*), dan pewarisan konteks (*task-local values & priority*) antara:
1. Structured Concurrency: `async let` dan `withTaskGroup(of:returning:body:)`
2. Unstructured Concurrency: `Task { }`
3. Detached Tasks: `Task.detached { }`

Kapan seorang arsitek sistem harus secara eksplisit menolak penggunaan `Task.detached` demi kestabilan context-inheritance di UI thread?

### Soal 1.3: Isolasi `@MainActor` dan Konteks Boundary
Jelaskan bagaimana anotasi `@MainActor` dioperasikan di bawah kap mesin (*under the hood*). Mengapa pemanggilan metode `@MainActor` dari *actor* independen atau *non-isolated context* mewajibkan *keyword* `await`? Jelaskan pula bagaimana *compiler* Swift 6 menegakkan *compile-time synchronization* tanpa menggunakan *lock* tradisional (*mutex/os_unfair_lock*) pada boundary ini.

### Soal 1.4: Fenomena Actor Reentrancy
Swift Actor menjamin isolasi status (*state isolation*) dari *data races* fisik (memori), namun **tidak** menjamin *atomic execution* lintas *suspension points* (`await`). Jelaskan konsep *Actor Reentrancy*. Mengapa desain ini dipilih oleh tim bahasa Swift alih-alih *lock-based actor*, dan bagaimana kondisi ini dapat memicu *logical race conditions* jika *state invariants* tidak divalidasi ulang setelah titik `await`?

### Soal 1.5: Kontrak Semantik Protokol `Sendable`
Analisis perbedaan perlakuan *compiler* terhadap:
1. Implicitly Sendable Types (Value Types)
2. `final class` dengan `Sendable` conformance manual
3. `@unchecked Sendable`

Jelaskan risiko arsitektural penggunaan `@unchecked Sendable` pada aplikasi enterprise dan kondisi absolut apa saja yang harus dipenuhi sebelum seorang engineer diizinkan menandai tipe data dengan atribut tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Cooperative Thread Starvation
Bayangkan sebuah modul komputasi kriptografi intensif dieksekusi di dalam blok `Task { ... }` tanpa titik *suspension* (`await`). Beberapa saat kemudian, animasi UI di `@MainActor` mengalami *micro-stutter* dan *task* lain di background berhenti dieksekusi secara serentak. 
1. Mengapa eksekusi synchronous intensif di *cooperative pool* dapat menyebabkan *thread starvation*?
2. Bagaimana cara mengidentifikasi masalah ini menggunakan Instruments (*System Trace / Swift Concurrency template*)?
3. Apa solusi refaktor berbasis `Task.yield()` atau pemindahan ke *custom dispatch queue* khusus?

### Soal 2.2: Mekanisme Pembatalan Kooperatif pada Modifikasi `.task(id:)`
Diberikan modifier SwiftUI `.task(id: queryText) { await search() }`. 
1. Jelaskan urutan pemanggilan internal yang terjadi saat nilai `queryText` berubah sebelum eksekusi `search()` pertama selesai.
2. Mengapa menambahkan `await Task.sleep(...)` otomatis menghormati pembatalan, sementara pemrosesan data menggunakan loop synchronous `for item in items` tidak merespons pembatalan?
3. Implementasikan pola pengecekan pembatalan manual yang benar di dalam operasi synchronous panjang menggunakan `Task.isCancelled` dan `Task.checkCancellation()`.

### Soal 2.3: Backpressure & Buffering Strategy pada `AsyncStream`
Jelaskan arsitektur producer-consumer menggunakan `AsyncStream`. Bandingkan konfigurasi `AsyncStream.Continuation.BufferingPolicy`:
- `.unbounded`
- `.bufferingNewest(Int)`
- `.bufferingOldest(Int)`

Jika sebuah modul network socket memancarkan data 10.000 events/detik sementara konsumsi di SwiftUI layer hanya mampu memproses 60 frame/detik:
- Kebijakan buffering mana yang mencegah *high memory footprint* (*OOM crash*)?
- Bagaimana menangani siklus pembatalan stream melalui callback `onTermination` agar tidak terjadi *resource leak* pada koneksi TCP underlying?

### Soal 2.4: Crossing Isolation Domains di Swift 6 Strict Concurrency
Diberikan konfigurasi *Strict Concurrency Checking* disetel ke `Complete` (`-strict-concurrency=complete`). Sebuah method di `@MainActor class ViewModel` memanggil background utility:

```swift
actor DataEngine {
    func process(handler: @escaping () -> Void) { ... }
}
```

Compiler Swift 6 memunculkan error: `Passing closure as argument to actor-isolated method introduces a data race`.
1. Bedah mengapa closure tersebut dianggap sebagai vektor pembawa *data race*.
2. Bagaimana signature closure harus diubah menggunakan `@Sendable`?
3. Apa implikasi struktural jika closure tersebut menangkap (`capture`) referensi dari `ViewModel`?

### Soal 2.5: Priority Inversion & Dynamic Priority Escalation
Jelaskan skenario di mana *Priority Inversion* dapat terjadi di Swift Concurrency ketika sebuah `Task(priority: .background)` memegang akses eksklusif ke sebuah `actor`, sementara `Task(priority: .userInteractive)` mencoba memanggil metode pada `actor` yang sama. Bagaimana runtime Swift Concurrency melakukan *Dynamic Priority Escalation* untuk menyelesaikan kondisi ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Deadlock & Thread Starvation pada High-Frequency Trading App
Sebuah aplikasi analitik finansial mengalami *freeze* total (ANR - *Application Not Responding*) secara intermiten pada kondisi lonjakan pasar (*high volatility*). 

**Arsitektur Saat Ini:**
- Backend streaming memompa data harga via WebSocket.
- Handler pesan WebSocket menggunakan `Task.detached(priority: .high)` untuk setiap pesan yang masuk.
- Di dalam Task, engineer melakukan:
  ```swift
  Task.detached(priority: .high) {
      let decoded = try JSONDecoder().decode(PriceTick.self, from: data)
      await OrderBookActor.shared.update(tick: decoded)
      let summary = OrderBookActor.shared.blockingCalculateSpread() // Synchronous C-library call
      await MainActor.run {
          self.renderTicker(summary)
      }
  }
  ```

**Tugas Diagnostik & Arsitektur Anda:**
1. Analisis titik kritis keruntuhan (*collapse point*) arsitektur di atas sehubungan dengan kapasitas *cooperative thread pool*.
2. Mengapa eksekusi `OrderBookActor.shared.blockingCalculateSpread()` merusak kestabilan thread pool global?
3. Rancang arsitektur refaktor menyeluruh yang memanfaatkan:
   - Throttling/Batching stream.
   - Isolasi komputasi blocking ke dedicated background thread (non-cooperative).
   - Penjaminan UI refresh rate tetap terjaga tanpa starvation.

---

### Skenario B: Race Condition Finansial akibat Actor Reentrancy
Pada aplikasi digital banking, tim mendapati laporan adanya akun pengguna yang berhasil menarik saldo melebihi batas simpanan (*negative balance anomaly*) saat melakukan transaksi tarik tunai secara beruntun dengan latensi jaringan tinggi.

**Kode Bermasalah:**
```swift
actor AccountManager {
    private var balance: Decimal = 1000

    func withdraw(amount: Decimal) async throws -> TransactionReceipt {
        guard balance >= amount else {
            throw BankingError.insufficientFunds
        }
        
        // Network call ke payment gateway
        let authCode = try await PaymentGateway.shared.authorize(amount: amount)
        
        // Mutasi saldo
        balance -= amount
        return TransactionReceipt(authCode: authCode, remainingBalance: balance)
    }
}
```

**Tugas Diagnostik & Arsitektur Anda:**
1. Bedah secara kronologis bagaimana *Actor Reentrancy* memungkinkan dua panggilan `withdraw(amount: 800)` yang dieksekusi secara konkuren berhasil lolos verifikasi `guard balance >= amount`, menghasilkan saldo akhir `-600`.
2. Jelaskan mengapa membungkus method dengan `actor` gagal memitigasi *logical race condition* ini.
3. Tulis ulang kode di atas dengan mengimplementasikan pola *State Reservation Pattern* atau *Transaction Token Pattern* yang memastikan atomisitas transaksi tetap utuh lintas *suspension point*.

---

### Skenario C: Migrasi Arsitektur Reaktif Legacy ke Swift 6 `@Observable`
Sebuah enterprise codebase berskala besar sedang dimigrasikan dari Combine (`ObservableObject`, `@Published`, `CurrentValueSubject`) ke Swift Concurrency murni (`@Observable` macro + Swift 6 Strict Concurrency).

**Dilema Arsitektur:**
Sebagian tim menginginkan seluruh `ViewModel` dideklarasikan sebagai `@MainActor final class`, sementara arsitek data menginginkan ViewModel bebas isolasi (*non-isolated*) dan hanya mem-bind data via *isolated properties* guna menghindari beban berlebih pada *Main Thread*.

**Tugas Diagnostik & Arsitektur Anda:**
1. Evaluasi trade-off performa rendering SwiftUI: Apa konsekuensi runtime jika operasi *mapping/formatting* model kompleks dilakukan langsung di dalam `@MainActor ViewModel`?
2. Bagaimana `@Observable` menangani *thread-dispatching* saat mutasi data terjadi? Apakah ada garansi bahwa modifikasi *property* `@Observable` otomatis aman jika dipanggil dari background task tanpa `@MainActor`?
3. Definisikan standar arsitektur baku (*Enterprise Guideline*) untuk tim Anda: Kapan ViewModel harus diisolasi penuh ke `@MainActor`, dan bagaimana memisahkan *Heavy Business Logic / Aggregation Layer* ke `actor` terpisah secara bersih (*clean boundary crossing*).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Resilience Real-Time Telemetry Processing Engine

#### Problem Statement
Anda diminta membangun fondasi sistem pemrosesan telemetri armada logistik (*Fleet Telemetry Dashboard*) pada iPadOS. Aplikasi menerima ribuan paket telemetri per detik melalui *mock stream*, memvalidasi integritas data, memperkaya (*enrich*) data dengan lokasi offline menggunakan lookup geofence, dan menampilkan metrik agregasi langsung pada antarmuka SwiftUI dengan performa solid 60/120 FPS tanpa penurunan frame (*zero dropped frames*).

#### Architectural Requirements
1. **Telemetry Receiver (AsyncStream):**
   - Buat `TelemetryHub` yang membungkus incoming network socket buatan menjadi `AsyncStream<RawTelemetryPacket>`.
   - Implementasikan *backpressure management* menggunakan strategi `.bufferingNewest(maxCapacity: 100)`.
   - Pastikan pemutusan stream melepaskan resource underlying secara deterministik via `onTermination`.
2. **Concurrent Processor (TaskGroup):**
   - Bangun `TelemetryProcessor` actor yang mengonsumsi stream.
   - Proses pengayaan data telemetri harus dieksekusi menggunakan *Structured Concurrency* (`withTaskGroup`).
   - Batasi konkurensi pemrosesan paralel maksimal sebanyak 4 concurrent child tasks secara konstan untuk menghindari saturasi CPU (*Worker Pool Pattern* di dalam task group).
3. **State Engine & Actor Reentrancy Protection:**
   - Simpan status metrik armada di dalam `FleetStatusEngine` actor.
   - Sediakan mekanisme pendaftaran telemetry point dengan proteksi reentrancy penuh (validasi mutasi lokal sebelum dan sesudah *suspension points*).
4. **SwiftUI Presentation Layer:**
   - Buat View dengan modifier `.task(id:)` yang mendengarkan perubahan status armada.
   - Anotasikan seluruh antarmuka interaktif dan ViewModel terkait secara ketat pada konteks `@MainActor`.
   - Implementasikan *cooperative cancellation*: Jika pengguna keluar dari layar pemantauan atau memilih armada lain, pipeline pemrosesan telemetri yang sedang berjalan harus berhenti seketika.

#### Constraints
- Proyek harus lulus kompilasi dengan flag Swift 6 `-strict-concurrency=complete` tanpa satu pun warning (*Zero Concurrency Warnings*).
- Dilarang keras menggunakan `DispatchQueue`, `NSLock`, atau `@unchecked Sendable`.
- Tidak boleh memblokir thread utama: Seluruh parsing dan kalkulasi agregasi kompleks harus diverifikasi berjalan di luar main thread melalui Instruments/Thread-logger assertions.

#### Expected Output
Kode Swift terpadu yang modular (Production-grade), mencakup:
- Struct/Model yang *Sendable-compliant*.
- Implementasi `TelemetryHub`, `TelemetryProcessor`, dan `FleetStatusEngine`.
- Implementasi View SwiftUI dan ViewModel pendukung.
- Verifikasi logika cancellation handling dan throttling logic.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memvalidasi kesiapan teknis sebelum melangkah ke bab arsitektur berikutnya.

### Saya harus memahami:
- [ ] Perbedaan fundamental antara model threading GCD (OS managed / unbounded) dan Cooperative Thread Pool Swift Concurrency (CPU-core bound).
- [ ] Mengapa `Task.detached` memutus Task-Local values, Actor isolation, dan QoS inheritance.
- [ ] Mekanisme kerja Actor Reentrancy dan bahaya tersembunyi terhadap *state invariants* di sekitar kata kunci `await`.
- [ ] Aturan ketat protokol `Sendable`, perbedaan antara *thread safety* via *immutability* vs *actor isolation*.
- [ ] Cara runtime Swift Concurrency mendistribusikan eksekusi closure pada boundary `@MainActor`.
- [ ] Perilaku siklus hidup SwiftUI modifier `.task` (kapan dibuat, kapan di-*cancel*, dan keterikatannya dengan View identity).
- [ ] Dampak pemanggilan blocking synchronous APIs (`pthread_mutex`, blocking I/O) di dalam Cooperative Pool.

### Saya tidak perlu menghafal:
- [ ] Format biner exact dari Swift Async ABI task frame pada level register/assembly CPU.
- [ ] Nilai integer absolut dari bitmask flags internal pada *Swift Concurrency runtime structures*.
- [ ] Detail algoritma scheduling thread kernel XNU internal yang menangani Core OS task dispatching.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengompilasi proyek di bawah flag `-strict-concurrency=complete` (Swift 6 mode) dengan nol warning.
- [ ] Menggunakan Xcode Instruments (*Swift Concurrency Template*) untuk melacak *Task Creation*, *Task Suspension*, *Actor Contention*, dan *Thread Starvation*.
- [ ] Mengubah callback-based API warisan (*delegates / completion handlers*) menjadi Swift Concurrency modern menggunakan `withCheckedThrowingContinuation` secara aman (mencegah *continuation leak* & *double-resume*).
- [ ] Mengimplementasikan *Worker Pool Pattern* menggunakan `withTaskGroup` untuk membatasi jumlah operasi paralel yang berjalan simultan.
- [ ] Merancang state mutator di dalam Swift Actor yang kebal terhadap *actor reentrancy data corruption*.
- [ ] Mengintegrasikan pipeline asynchronous ke komponen deklaratif SwiftUI menggunakan lifecycle `.task` dan `@Observable` secara presisi tanpa memicu *redundant view redraws*.