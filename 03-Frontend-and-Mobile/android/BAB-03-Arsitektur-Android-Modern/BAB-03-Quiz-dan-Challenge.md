# BAB 03: Quiz, Challenge, & Knowledge Check
**Arsitektur Android Modern (Clean Architecture, MVI, & UDF)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dependency Inversion Principle & Purity of Domain Layer
Jelaskan secara matematis dan arsitektural mengapa modul `Domain` pada Clean Architecture murni Android modern **tidak boleh** memiliki dependensi terhadap framework Android (`import android.*`) maupun runtime database/network (Room/Retrofit). Bagaimana penerapan *Dependency Inversion Principle* (DIP) memfasilitasi pemisahan ini, dan apa trade-off runtime performance yang harus dibayar saat melakukan pemetaan objek (*data mapping*) antar layer?

### Soal 1.2: Unidirectional Data Flow (UDF) vs Bidirectional Binding
Bandingkan paradigma *Unidirectional Data Flow* (UDF) dengan *Bidirectional Data Binding* (seperti `Two-way DataBinding` era legacy MVVM) dalam konteks determinisme state aplikasi mobile. Analisis bagaimana UDF mengeliminasi masalah *split-brain state* dan *circular state invalidation* ketika UI menerima input concurrent dari pengguna dan background WebSocket secara simultan.

### Soal 1.3: Anatomi MVI: State vs. Side-Effect vs. Intent
Secara formal, arsitektur MVI dapat dimodelkan sebagai state machine: $f(\text{State}_n, \text{Intent}) \to \text{State}_{n+1}$.
1. Definisikan batasan semantik antara **State** (keadaan kontinu) dan **Side-Effect / Event** (transient/one-off).
2. Mengapa merepresentasikan *Snackbar error* atau *Navigation command* sebagai properti `Boolean` di dalam data class `UiState` dianggap sebagai *anti-pattern* fatal dalam deklaratif UI (Jetpack Compose)?

### Soal 1.4: Primitive State Streaming: StateFlow vs. SharedFlow vs. Channel
Dalam implementasi MVI berbasis Kotlin Coroutines:
* Kapan Anda harus menggunakan `StateFlow`, `SharedFlow`, dan `Channel`?
* Jelaskan perbedaan mekanisme penanganan *backpressure*, *replay cache*, dan *subscriber lifecycle awareness* di antara ketiganya saat UI berpindah dari status `STARTED` ke `STOPPED`.

### Soal 1.5: Granularitas & Lifecycle UseCase
Dalam Clean Architecture, apa justifikasi teknis menerapkan *Single-Responsibility UseCase* (satu UseCase hanya mengekspos satu fungsi public/operator `invoke`) dibandingkan mengelompokkan operasi domain ke dalam `Service` atau langsung mengakses `Repository` dari ViewModel? Kapan pembuatan UseCase menjadi *over-engineering*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Recomposition Storms Akibat Polusi Unstable Types pada UiState
Perhatikan potongan kode UI State berikut:
```kotlin
data class DashboardUiState(
    val isLoading: Boolean = false,
    val userBalance: BigDecimal = BigDecimal.ZERO,
    val transactions: List<TransactionModel> = emptyList() // java.util.List
)
```
Jetpack Compose Compiler menandai `DashboardUiState` di atas sebagai **unstable**. Jelaskan mekanisme internal Compose compiler (*Stability Inference*) yang menyebabkan seluruh komponen UI yang membaca `transactions` mengalami recomposition berulang secara agresif meskipun datanya tidak berubah. Bagaimana Anda memperbaikinya menggunakan `@Immutable` / `@Stable` atau library `kotlinx.collections.immutable`?

### Soal 2.2: Memory Leak & Event Loss pada Channel-based Effect Handler
Diberikan implementasi side-effect berikut pada ViewModel:
```kotlin
private val _effect = Channel<UiEffect>(Channel.BUFFERED)
val effect = _effect.receiveAsFlow()
```
Dan di sisi UI:
```kotlin
LaunchedEffect(Unit) {
    viewModel.effect.collect { effect ->
        handleEffect(effect)
    }
}
```
Identifikasi 2 (dua) kegagalan fatal dari pendekatan ini ketika terjadi *configuration change* (rotasi layar) dan ketika coroutine UI terhenti karena lifecycle berada di bawah `Lifecycle.State.STARTED`. Tuliskan pola standar industri yang tepat menggunakan `repeatOnLifecycle`.

### Soal 2.3: Anti-Pattern `flowOn` dan Concurrency Leakage pada Clean Architecture
Sebuah tim mengimplementasikan UseCase sebagai berikut:
```kotlin
class GetFinancialReportUseCase @Inject constructor(
    private val repository: ReportRepository
) {
    operator fun invoke(): Flow<Report> = repository.getStream()
        .map { transformData(it) }
        .flowOn(Dispatchers.IO) // <--- Line A
}
```
Mengapa meletakkan `.flowOn(Dispatchers.IO)` di level UseCase (Line A) dapat melanggar prinsip enkapsulasi threading dan menyebabkan *thread exhaustion* pada aplikasi berskala besar? Di layer manakah `CoroutineDispatcher` seharusnya di-inject, dan bagaimana struktur abstractions-nya agar 100% *unit-testable* tanpa `Dispatchers.setMain` mengotori background test?

### Soal 2.4: Atomic State Mutation vs. Non-Atomic Read-Modify-Write
Dua buah coroutine concurrent mengeksekusi update state berikut di ViewModel:
```kotlin
// Thread A & Thread B memanggil fungsi ini hampir bersamaan
fun markItemAsRead(itemId: String) {
    viewModelScope.launch {
        val currentList = _uiState.value.items
        val updatedList = currentList.map { if (it.id == itemId) it.copy(isRead = true) else it }
        _uiState.value = _uiState.value.copy(items = updatedList)
    }
}
```
Jelaskan bagaimana race condition terjadi pada operasi di atas sehingga menyebabkan *lost update*. Tuliskan solusi thread-safe atomik menggunakan `MutableStateFlow.update { }` dan jelaskan mekanisme perbandingannya (*CAS - Compare-And-Swap*) di balik layar.

### Soal 2.5: Restorasi State Pasca Process Death pada MVI
`StateFlow` mempertahankan state secara in-memory, namun hancur saat OS melakukan *System-initiated Process Death*. Bagaimana arsitektur UDF mengintegrasikan `SavedStateHandle` tanpa merusak konsep *Single Source of Truth* (SSOT)? Jelaskan strategi serialisasi state yang kompleks tanpa membebani *Binder Transaction Buffer* (yang memiliki limit 1MB).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: State Explosion & UI Freezing pada Aplikasi High-Frequency Crypto OrderBook
* **Konteks:** Anda adalah Tech Lead pada aplikasi perdagangan kripto. Aplikasi Anda menerima feed data OrderBook via WebSocket dengan frekuensi rata-rata 30-50 payload per detik.
* **Masalah:** Menggunakan pendekatan MVI standar, setiap update data menghasilkan instance baru `OrderBookUiState` dan di-emit via `MutableStateFlow`. Pengguna melaporkan aplikasi mengalami degradasi frame rate drastis (drop dari 120 FPS ke 14 FPS), konsumsi baterai ekstrem, dan UI freeze selama masa volatilitas pasar tinggi.
* **Pertanyaan Diagnostik:**
  1. Analisis mengapa emisi state granular berfrekuensi tinggi menghancurkan performa pipeline Jetpack Compose (fokus pada Phase: *Composition*, *Layout*, *Draw*).
  2. Rancang arsitektur buffer state menggunakan coroutine operators (misal: `conflate`, `sample`, atau batching custom) untuk memisahkan kecepatan konsumsi UI (maksimum 60/120 Hz) dari kecepatan data feed backend.
  3. Bagaimana struktur hierarki `UiState` dipecah agar area OrderBook yang tidak berubah tidak terpaksa di-recompose saat ticker harga bergerak?

### Skenario B: Race Condition & Data Corruption pada Optimistic Cart Synchronization
* **Konteks:** Aplikasi E-Commerce menerapkan *Optimistic UI Update* pada keranjang belanja. Ketika pengguna menekan tombol "+", MVI State langsung mengupdate UI (`quantity = n + 1`), lalu secara asinkron menembakkan UseCase ke local database (Room) dan network API.
* **Masalah:** Pengguna menekan tombol "+" secara agresif (5 kali dalam 800ms) pada koneksi *flaky* (EDGE/3G). Beberapa request API gagal dengan `HTTP 504 Timeout`, sementara yang lain sukses namun urutan responsnya acak (*out-of-order response*). Akibatnya, angka keranjang di UI melompat-lompat (contoh: 1 -> 2 -> 3 -> 2 -> 5 -> 3) dan nilai akhir di lokal berbeda dengan database server.
* **Pertanyaan Diagnostik:**
  1. Tunjukkan kecacatan desain flow data pada kasus di atas. Mengapa optimistic update tanpa *versioning* atau *transaction rollback queue* berakibat fatal pada sistem UDF?
  2. Rancang diagram sequence dan logic reducer MVI yang menerapkan state reconciliation, *Command Queuing*, dan *Rollback mechanism* yang deterministik saat request network gagal.

### Skenario C: Architectural Leaks pada Migrasi Legacy Monolith ke Multi-Module Clean Architecture
* **Konteks:** Perusahaan fintech memutuskan melakukan migrasi dari aplikasi monolitik MVVM ke modular Clean Architecture (terdiri dari module: `:core:model`, `:domain:wallet`, `:data:wallet`, `:feature:wallet`).
* **Masalah:** Developer di tim Anda membuat entitas Room `@Entity data class WalletEntity` di dalam modul `:data:wallet`. Karena deadline ketat, developer tersebut langsung mengimpor `WalletEntity` ke dalam `WalletUiState` di modul `:feature:wallet` dan me-render-nya di Compose UI. Ketika backend mengubah tipe data field mata uang dari `Double` ke `String` (ISO-4217), kompilasi di modul `:feature` rusak dan tes unit di domain tidak mendeteksi breaking change.
* **Pertanyaan Diagnostik:**
  1. Berdasarkan aturan *Clean Architecture Dependency Rule*, jelaskan semua pelanggaran yang terjadi pada skenario tersebut.
  2. Rancang model representasi data yang benar untuk ketiga layer tersebut (`Entity/DTO` di Data, `Domain Model` di Domain, dan `UiState/UiModel` di Presentation) beserta strategi mapping (*Anti-Corruption Layer*).
  3. Buat implementasi verifikasi otomatis (misalnya aturan ArchUnit atau deteksi custom detekt/Gradle API dependency constraints) untuk memblokir impor layer data secara permanen dari layer presentation.

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Offline-First MVI State Machine Engine dengan UDF & Optimistic Updates
Rancang dan implementasikan engine state terisolasi untuk fitur **"Real-Time Stock Watchlist & Transaction Simulator"**.

#### Requirements:
1. **Domain Purity:**
   * Bangun domain layer 100% pure Kotlin (bebas Android framework).
   * Gunakan Functional Error Handling (`Result<T>` custom atau `Arrow-kt Either`) tanpa melempar exception liar (`no untamed throws`).
2. **Deterministic MVI State Machine:**
   * Buat class Reducer terpusat: `(PreviousState, UiIntent) -> ReducerResult(NewState, Set<SideEffect>)`.
   * Modelkan state UI secara komprehensif menggunakan Kotlin Sealed Interface / Value Classes:
     * Loading, Content, Error, Offline-Degraded.
   * State harus memenuhi syarat Compose Compiler Stability (gunakan immutable collections).
3. **Optimistic Updates with Event Reconciliation:**
   * Pengguna dapat mengubah alokasi "Target Investment" secara lokal. State langsung berubah.
   * Gunakan background channel untuk sinkronisasi ke Mock Network Engine.
   * Jika server me-reject transaksi (misal: "Insufficient Liquidity"), engine harus secara otomatis memicu rollback state ke snapshot valid terakhir dan memancarkan `OneOffEffect.ShowSnackbarToast`.
4. **Execution Flow Control:**
   * Terapkan pencegahan double-dispatch pada event klik / input pengguna (*action debouncing/throttling*).
   * Stream data real-time harga saham disimulasikan menggunakan hot flow (`SharedFlow`), di-*sample* agar tidak membebani collector.

#### Engineering Constraints:
* **Threading Safety:** State reducer wajib bersifat strictly thread-safe dan non-blocking. State mutations harus serial dan atomik.
* **Lifecycle Awareness:** Collector effect dan state pada UI harus aman dari kebocoran memori saat screen lifecycle berada di background.
* **Zero UI Event Loss:** Efek navigasi dan error tidak boleh hilang saat terjadi pergantian konfigurasi (layar diputar).

#### Expected Output:
1. Kode arsitektur modular mencakup:
   * Contract Interface (`UiState`, `UiIntent`, `UiEffect`).
   * Reducer logic + UseCase interactor.
   * ViewModel yang mengekspos `StateFlow<UiState>` dan `Flow<UiEffect>`.
2. Unit Test komprehensif menggunakan **Turbine** dan **MockK / Fake Repositories** yang memvalidasi:
   * State transitions dari Intent $\to$ New State.
   * Rollback scenario ketika network call menghasilkan error.
   * Verifikasi emisi One-Off Side Effect.
   * Test coverage pada Business Logic minimal 90%.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan mutlak *Clean Architecture Dependency Rule* (ketergantungan hanya boleh mengarah ke dalam, menuju Domain).
- [ ] Formula matematis dan siklus tertutup *Unidirectional Data Flow* (UDF): User Action $\to$ Intent $\to$ Processor/UseCase $\to$ Reducer $\to$ State $\to$ UI Render.
- [ ] Mengapa *State* harus bersifat persistent & durable, sedangkan *Effect* bersifat transient & single-consumption.
- [ ] Konsep *Stability* pada Jetpack Compose Compiler (`@Immutable`, `@Stable`, structural equality vs reference equality).
- [ ] Mekanisme kerja `MutableStateFlow.update { }` berbasis Atomic CAS (*Compare-And-Swap*) loop.
- [ ] Perbedaan fundamental antara `Channel.BUFFERED`, `Channel.CONFLATED`, dan dampaknya terhadap event retention.
- [ ] Mengapa Domain layer tidak boleh terikat pada `lifecycle-viewmodel` atau runtime concurrency platform-specific jika ingin portabel (misal ke KMP).
- [ ] Konsep *Anti-Corruption Layer* (ACL) saat memetakan DTO API/Database ke Domain Entities dan Presentation Models.

### Saya tidak perlu menghafal:
- [ ] Seluruh signature parameter konfigurasi Room `@Entity` atau detail anotasi Retrofit serializer.
- [ ] Sintaks persis DSL build.gradle untuk dependency injection tools (Hilt/Koin), fokuslah pada konsep abstraksi graf dependensi.
- [ ] Boilerplate mapping manual baris-per-baris; pahami mengapa pemisahan model itu penting, bukan menghafal nama fungsi ekstensi konversinya.

### Saya harus bisa melakukan:
- [ ] Memisahkan arsitektur proyek Android monolitik menjadi minimal 3 layer terisolasi (`Data`, `Domain`, `Presentation`).
- [ ] Mendiagnosis dan menghentikan *recomposition storm* pada Compose Layout menggunakan Layout Inspector dan Compose Compiler Metrics.
- [ ] Mengimplementasikan *Single-State Reducer Pattern* yang aman dari race condition menggunakan Kotlin Coroutines & Flow.
- [ ] Mengonsumsi `UiEffect` secara aman pada Jetpack Compose menggunakan lifecycle API modern (`collectAsStateWithLifecycle` dan `repeatOnLifecycle`).
- [ ] Menulis unit test untuk asynchronous stream kompleks menggunakan library `Turbine` dengan assertion atomik pada setiap emisi state.
- [ ] Memulihkan state aplikasi pasca simulasi *Process Death* (`Don't keep activities` / ADB kill process) dengan `SavedStateHandle`.