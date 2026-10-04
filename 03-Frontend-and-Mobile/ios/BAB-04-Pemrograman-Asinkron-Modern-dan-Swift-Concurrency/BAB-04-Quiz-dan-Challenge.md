# BAB 04: Quiz, Challenge, & Knowledge Check
**Pemrograman Asinkron Modern & Swift Concurrency**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Suspensi pada `async/await` vs Context Switching OS**  
   Jelaskan secara mendalam apa yang terjadi pada *call stack* dan alokasi *thread* ketika sebuah fungsi Swift mencapai *suspension point* (`await`). Bandingkan proses pelepasan *underlying OS thread* ini dengan *preemptive context switching* tradisional pada Grand Central Dispatch (GCD) atau POSIX threads!

2. **Structured Concurrency vs Unstructured Tasks**  
   Uraikan perbedaan arsitektural dan siklus hidup (*lifecycle*) antara Structured Concurrency (`async let`, `withTaskGroup`) dan Unstructured Concurrency (`Task.init`, `Task.detached`). Bagaimana *task hierarchy* memengaruhi propagasi prioritas (*priority propagation*), *cancellation context*, dan *error handling* antar *parent* dan *child task*?

3. **Actor Model dan Enkapsulasi State**  
   Bagaimana Swift Actor menjamin eliminasi *data race* pada level kompilasi (*compile-time safety*)? Jelaskan mengapa Actor di Swift menggantikan kebutuhan *serial dispatch queue* manual, dan jelaskan konsep *executor* yang mendasari eksekusi pesan secara asinkron di dalam Actor.

4. **Semantik Protokol `Sendable` dan *Isolation Boundaries***  
   Mengapa sistem tipe Swift membutuhkan marker protocol `Sendable`? Analisis kondisi apa saja yang membuat sebuah `class`, `struct`, `enum`, atau *closure* memenuhi syarat sebagai *Sendable*, serta jelaskan konsekuensi arsitektural dari penggunaan `@unchecked Sendable` dalam kode produksi.

5. **`@MainActor` dan Runtime Executor Hopping**  
   Jelaskan bagaimana anotasi `@MainActor` mengikat eksekusi fungsi atau mutasi *property* ke *main thread*. Ketika sebuah fungsi asinkron non-isolated memanggil fungsi beranotasi `@MainActor`, jelaskan mekanisme *executor hopping* yang terjadi di runtime dan dampaknya terhadap performa jika terjadi secara berulang dalam *tight loop*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Cooperative Thread Pool Starvation & Forward Progress Guarantee**  
   Swift Concurrency mengandalkan *cooperative thread pool* dengan jumlah *thread* maksimal yang dibatasi sesuai jumlah core CPU fisik/logis. Apa yang terjadi secara runtime jika sebuah fungsi asinkron mengeksekusi operasi sinkronus pemblokir (*blocking I/O* atau `Thread.sleep` alih-alih `Task.sleep`)? Bagaimana skenario ini memicu *thread starvation* sistem secara global dan bagaimana strategi mitigasinya?

2. **Actor Reentrancy & State Inconsistency**  
   Amati cuplikan konseptual berikut:
   ```swift
   actor AccountManager {
       var balance: Double = 100.0
       
       func debit(amount: Double) async throws {
           guard balance >= amount else { throw InsufficientFundsError() }
           try await networkService.logTransaction(amount: amount)
           balance -= amount
       }
   }
   ```
   Identifikasi kelemahan konkurensi kritis (*concurrency bug*) pada kode di atas terkait *Actor Reentrancy*. Mengapa pemanggilan `await` di tengah fungsi dapat menyebabkan nilai `balance` menjadi negatif meskipun telah divalidasi oleh `guard`, dan bagaimana pola refaktorisasi defensif yang benar?

3. **Mekanisme Task Cancellation: Polling vs Cancellation Handler**  
   Pembatalan (*cancellation*) dalam Swift Concurrency bersifat kooperatif (*cooperative*). Jelaskan perbedaan mendasar antara melakukan *polling* status via `Task.isCancelled` / `Task.checkCancellation()` dengan mendaftarkan closure melalui `withTaskCancellationHandler(operation:onCancel:)`. Kapan Anda wajib menggunakan `withTaskCancellationHandler` saat berinteraksi dengan API eksternal berbasis sinkronisasi atau non-cancellable?

4. **Invarian `CheckedContinuation` dan Konsekuensi Pelanggarannya**  
   Ketika menjembatani API *closure-based legacy* menggunakan `withCheckedThrowingContinuation`, runtime Swift memberlakukan aturan absolut: *continuation harus di-resume tepat satu kali (exactly-once execution)*. Jelaskan secara teknis apa dampak fatal yang terjadi jika:
   - *Continuation* dipanggil lebih dari satu kali (`resumed twice`).
   - *Continuation* tidak pernah dipanggil sama sekali (`abandoned continuation / leaked task`).

5. **Custom Actor Executors (Swift 5.9+) dan Thread Confinement**  
   Mengapa Swift 5.9 memperkenalkan protokol `SerialExecutor` untuk Custom Actor Executors? Jelaskan *use-case* tingkat lanjut di mana aplikasi memerlukan aktor khusus yang terikat pada *dedicated OS thread* atau *custom dispatch queue* (misalnya: operasi integrasi SQLite C-API atau manipulasi frame grafis audio real-time).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Crash "Watchdog Timeout" Akibat Deadlock Migrasi GCD ke Swift Concurrency
Sebuah aplikasi *fintech* enterprise sedang dalam proses migrasi bertahap dari GCD ke Swift Concurrency. Pengguna di produksi melaporkan bahwa aplikasi sering mengalami *freeze* total (ANR) dan dihentikan paksa oleh sistem operasi dengan laporan crash `0x8badf00d` (watchdog termination). 

Setelah investigasi dump stack trace, ditemukan pola pemanggilan berikut pada komponen inisialisasi lokal:
```swift
// Berjalan di Main Thread (View Controller Lifecycle)
let result = DispatchQueue.main.sync {
    return Task { @MainActor in
        return await DependencyContainer.shared.fetchCriticalConfig()
    }
}
// atau kode legacy yang memanggil semaphore.wait() pada Task asinkron:
let semaphore = DispatchSemaphore(value: 0)
Task {
    await someAsyncWork()
    semaphore.signal()
}
semaphore.wait()
```
- **Pertanyaan Diagnostik:**
  1. Analisis secara mendalam mengapa kombinasi `DispatchSemaphore.wait()` atau `DispatchQueue.sync` dengan Swift Concurrency `Task` menghasilkan *unrecoverable deadlock* pada thread pool!
  2. Bagaimana arsitektur *forward-progress guarantee* Swift Concurrency dilanggar dalam skenario ini?
  3. Berikan solusi refaktorisasi arsitektur komprehensif tanpa memblokir thread, namun tetap menjamin dependensi konfigurasi terinisialisasi secara aman sebelum render UI dilakukan.

---

### Skenario B: Race Condition dan Double-Spend pada High-Frequency Trading App
Sebuah modul *crypto-wallet* menggunakan Actor untuk mengelola status transaksi. Ketika jaringan seluler pengguna tidak stabil, modul jaringan melakukan *retry* otomatis. Pada pengujian beban tinggi (*stress testing*), terdeteksi bahwa saldo dompet pengguna sesekali menjadi minus ketika beberapa *request* penarikan saldo dieksekusi hampir bersamaan via UI.

Kode implementasi yang ditemukan:
```swift
actor WalletActor {
    private(set) var availableBalance: Decimal = 1000
    private var inFlightWithdrawals: [UUID: Decimal] = [:]
    
    func withdraw(id: UUID, amount: Decimal) async throws -> TransactionReceipt {
        guard availableBalance >= amount else {
            throw WalletError.insufficientFunds
        }
        
        // Network call ke gateway perbankan
        let receipt = try await paymentGateway.charge(id: id, amount: amount)
        
        // Mutasi saldo pasca respons jaringan
        self.availableBalance -= amount
        return receipt
    }
}
```
- **Pertanyaan Diagnostik:**
  1. Buktikan secara matematis dan alur konkurensi bagaimana *race condition* terjadi pada method `withdraw` di atas, meskipun method tersebut diisolasi di dalam `actor`.
  2. Implementasikan mekanisme proteksi *Pessimistic Locking* atau *State Reservation (Two-Phase Commit)* di dalam actor untuk menjamin saldo diproteksi secara atomik di seluruh *suspension points* tanpa membocorkan state jika network gateway melempar *error*.

---

### Skenario C: Memory Spikes dan Backpressure Failure pada Real-Time Log Ingestion
Aplikasi logistik mengalirkan ribuan telemetri GPS per detik dari hardware eksternal menggunakan WebSocket. Tim menggunakan `AsyncThrowingStream` untuk mendistribusikan data ke modul analitik lokal yang menulis ke disk menggunakan CoreData/SQLite. 

Di perangkat dengan spektrum rendah, memori aplikasi melonjak tajam (*high memory footprint*) hingga memicu *Out-Of-Memory (OOM) Termination*, karena frekuensi data GPS yang datang jauh lebih cepat dibandingkan kecepatan operasi I/O penyimpanan database lokal.
- **Pertanyaan Diagnostik:**
  1. Mengapa `AsyncStream` / `AsyncThrowingStream` default dapat menyebabkan memory bloat tak terbatas jika produser dan konsumer memiliki disparitas performa (*consumer lagging behind*)?
  2. Jelaskan konsep *Backpressure* dan evaluasi opsi `BufferingPolicy` (`.bufferingNewest`, `.bufferingOldest`, `.unbounded`) pada `AsyncStream`. Kapan masing-masing policy harus dipilih?
  3. Bagaimana Anda merancang sistem aliran data reaktif menggunakan Swift Concurrency yang menghentikan sementara pembacaan soket (*flow control*) ketika konsumer sedang mengalami *throttling* atau *disk contention*?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance, Reentrant-Safe Media Pipeline dengan Coalescing & Priority Propagation
Dalam aplikasi berbagi video berkinerja tinggi, Anda ditugaskan membangun komponen infrastruktur inti: **`ResilientMediaPipelineActor`**. Modul ini bertanggung jawab mengunduh, mendekode, dan menyimpan aset media biner ke memori secara transparan.

#### Requirements Teknis:
1. **Request Coalescing (Task De-duplication):** Jika ada 10 pemanggil (*callers*) yang meminta aset biner dengan URL yang sama secara bersamaan, modul hanya boleh menjalankan **satu** koneksi jaringan aktif. Sembilan pemanggil lainnya harus menunggu hasil dari *single in-flight task* yang sama.
2. **Actor-Reentrancy & Safety:** Status internal tidak boleh rusak jika salah satu panggilan jaringan gagal atau dibatalkan di tengah jalan (*cancellation*).
3. **Priority & Task Cancellation Propagation:** Jika *caller* membatalkan `Task`-nya, pipeline harus memastikan pembatalan tersebut dipropagasikan ke operasi jaringan *hanya jika* tidak ada *caller* lain yang masih mendengarkan task yang sama.
4. **Resilient Retry Logic:** Implementasikan mekanisme *retry* dengan formula *Exponential Backoff with Jitter* secara murni menggunakan `Task.sleep` yang kooperatif terhadap *cancellation*.
5. **Bridge Legacy Callback:** Jembatani satu legacy C-library API (misalnya: `LegacyImageDecoder.decode(data, completion: @escaping (Result<DecodedImage, Error>) -> Void)`) menggunakan `withCheckedThrowingContinuation` secara aman tanpa kemungkinan *multiple resume* atau *leak*.

#### Constraints:
- Dilarang menggunakan *lock primitif* manual (`NSLock`, `pthread_mutex`) atau GCD (`DispatchQueue`). Seluruh isolasi state dan sinkronisasi **harus murni** menggunakan Swift Concurrency (`actor`, `Task`, `AsyncSequence`).
- Kode harus lolos kompilasi dengan mode Swift 6 Concurrency Strictness (`-strict-concurrency=complete`) tanpa ada *warning* terkait `Sendable` boundary.
- Hindari *unbounded memory accumulation* untuk mapping task yang telah selesai (*stale task cleanup*).

#### Expected Output:
Sebuah modul Swift modular berisi:
1. `actor ResilientMediaPipeline` yang mengimplementasikan API:
   ```swift
   public func fetchMedia(from url: URL, priority: TaskPriority?) async throws -> DecodedImage
   ```
2. Unit tests berbasis `XCTest` yang menyimulasikan:
   - Tes 1: 5 *concurrent requests* untuk URL yang sama dieksekusi, memverifikasi *network client* hanya terpanggil tepat 1 kali.
   - Tes 2: Simulasi *Task cancellation* pada 1 caller tanpa menghentikan caller lainnya.
   - Tes 3: Simulasi verifikasi penanganan kegagalan (*error propagation*) ke semua awaiting callers.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara *suspension* (`await`) dengan pemblokiran thread OS (`thread blocking`).
- [ ] Batasan kapasitas *Cooperative Thread Pool* Swift dan mengapa *deadlock* terjadi jika digabungkan dengan pemblokiran sinkronus GCD (`DispatchQueue.main.sync`).
- [ ] Fenomena *Actor Reentrancy*: status lokal aktor dapat dimutasi oleh task lain saat aktor sedang berada dalam status *suspended* di titik `await`.
- [ ] Aturan ketat `CheckedContinuation` (*exactly-once invocation*) dan teknik debugging memory leak akibat *abandoned continuation*.
- [ ] Mekanisme kerja `Sendable` dalam menjamin *thread-safety* saat data melintasi *isolation domain*.
- [ ] Konsep hierarki *Structured Concurrency*: bagaimana *lifecycle*, prioritas, dan pembatalan dipropagasi dari *parent* ke *child task*.
- [ ] Dampak runtime performa dari *Executor Hopping* ke dan dari `@MainActor`.

### Saya tidak perlu menghafal:
- [ ] Alamat memori internal dari register CPU saat runtime context switching terjadi.
- [ ] Implementasi assembly internal libdispatch / C++ runtime scheduler untuk cooperative pool.
- [ ] Seluruh nomor integer kode POSIX thread error.
- [ ] Setiap variasi konfigurasi compiler flag untuk strict concurrency di toolchain Xcode versi lama (cukup pahami level Swift 6 target).

### Saya harus bisa melakukan:
- [ ] Menulis dan mendokumentasikan kode asinkron yang lolos verifikasi kompilasi `-strict-concurrency=complete` tanpa warning.
- [ ] Mengidentifikasi dan merefaktor *race condition* yang disebabkan oleh *Actor Reentrancy* pada kode produksi.
- [ ] Melakukan migrasi API lama berbasis *completion handler callback* ke *async/await* menggunakan `withCheckedThrowingContinuation` secara aman dan anti-bocor.
- [ ] Membangun mekanisme *in-flight task deduplication (request coalescing)* menggunakan `Task` dictionary di dalam `actor`.
- [ ] Menangani *cooperative task cancellation* secara komprehensif menggunakan `Task.isCancelled` dan `withTaskCancellationHandler`.
- [ ] Menganalisis *Instruments Time Profiler* dan *Swift Concurrency Trace* untuk mendeteksi *thread starvation* atau *excessive context switches*.