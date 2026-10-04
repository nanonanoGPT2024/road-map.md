# Arsitektur Android Modern: Clean Architecture, MVI, & UDF

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** `03-Frontend-and-Mobile`
* **Jalur Pembelajaran:** Android Engineering
* **Bab / Modul:** Bab 03 / Modul 01
* **Topik Utama:** Arsitektur Android Modern (Clean Architecture, Model-View-Intent, & Unidirectional Data Flow)
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Pengetahuan:** Kotlin Coroutines & Flow, Jetpack Compose, Dependency Injection (Dagger/Hilt), Android Jetpack ViewModel, Dasar Pemrograman Reaktif.
* **Target Ekosistem:** Android SDK 34+, Kotlin 2.0+, Jetpack Compose Compiler 1.5+, Coroutines 1.8+.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara menyeluruh, engineer diharapkan mampu:

1. **Mendekomposisi Sistem Android Skala Enterprise:** Menerapkan prinsip *Separation of Concerns* (SoC) dan *Dependency Inversion Principle* (DIP) menggunakan Clean Architecture murni dengan pemisahan modul Gradle yang ketat (`:core:model`, `:core:domain`, `:core:data`, `:feature:x`).
2. **Merancang State Management Deterministik:** Mengabstraksikan interaksi pengguna dan siklus hidup sistem ke dalam paradigma *Unidirectional Data Flow* (UDF) dan *Model-View-Intent* (MVI) berbasis *finite state machine* (FSM).
3. **Mengeliminasi Concurrency Race Conditions:** Mengelola mutasi state menggunakan primitif konkurensi Kotlin Coroutines (`StateFlow`, `SharedFlow`, `Channel`) tanpa memicu mutasi parsial (*torn reads*) atau *state loss*.
4. **Mengisolasi Side Effects:** Mengimplementasikan pola penanganan efek samping (*one-off events*) seperti navigasi, *snackbar*, dan instrumentasi analitik tanpa melanggar prinsip idempoten Compose.
5. **Mengoptimalkan Kinerja Rendering:** Membangun struktur *Immutable State* yang mematuhi kontrak stabilitas Jetpack Compose Compiler untuk mencegah rekomposisi redundan (*skipping optimization*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Imperatif ke Deklaratif Deterministik

Dalam arsitektur Android tradisional (MVP atau MVVM imperatif berbasis `LiveData`), UI bertindak sebagai entitas pasif yang dimanipulasi secara sporadis dari berbagai *callback*:

```text
[Callback Jaringan] ───> view.showLoading(false)
                    └───> view.renderData(data)
[Klik Tombol]       ───> view.disableButton()
```

Pola ini rentan terhadap **State Drift**—kondisi di mana representasi visual UI tidak sinkron dengan data internal memori karena mutasi terjadi dari banyak jalur (*multidirectional mutations*).

**Mental Model MVI & UDF** memandang antarmuka pengguna sebagai fungsi matematika murni dari sebuah state:

$$\text{UI} = f(\text{State})$$

Setiap perubahan tampilan merupakan proyeksi visual langsung dari satu-satunya sumber kebenaran (*Single Source of Truth* / SSOT). UI tidak pernah mengubah state secara langsung. UI hanya memancarkan sinyal niat pengguna (**Intent**), yang diproses oleh mesin pemroses transisi state, menghasilkan state baru yang tidak dapat diubah (**Immutable State**), lalu dialirkan kembali ke UI.

```text
       ┌───────────┐
       │   State   │
       └─────┬─────┘
             │ (Merender Proyeksi Visual)
             ▼
       ┌───────────┐
       │    UI     │
       └─────┬─────┘
             │ (Memancarkan Aksi/Event)
             ▼
       ┌───────────┐
       │  Intent   │
       └───────────┘
```

### Analogi Sistem: Sistem Perbankan Event-Sourcing

Bayangkan rekening bank Anda. Saldo akhir Anda bukan sekadar variabel yang dapat ditimpa sembarangan oleh kasir, ATM, atau transfer online:
* **UI:** Mesin ATM yang menampilkan saldo Rp10.000.000 (State).
* **Intent:** Anda menekan tombol "Tarik Tunai Rp1.000.000" (User Action / Intent).
* **Domain/Reducer:** Sistem pusat menerima instruksi, memvalidasi limit, mendebet saldo melalui transaksi atomik, dan menerbitkan saldo baru Rp9.000.000.
* **Side Effect:** Mesin ATM mengeluarkan uang fisik dan mencetak struk (One-off Event).

Tidak ada pihak luar yang berhak mengubah saldo secara langsung tanpa melewati buku besar transaksi. Di Android Modern: State adalah saldo akhir, Intent adalah formulir instruksi, ViewModel/Reducer adalah buku besar, dan Side Effect adalah mesin pencetak fisik.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Tertutup Unidirectional Data Flow (UDF) & MVI

Aliran data bergerak dalam satu arah melingkar yang tertutup. Komponen UI hanya mengamati `StateFlow<UIState>` dan memicu `(UIIntent) -> Unit`.

```text
+---------------------------------------------------------------------------------------+
|                                      PRESENTATION                                     |
|                                                                                       |
|   +-----------------------+                         +-----------------------------+   |
|   |   Compose UI Screen   |                         |          ViewModel          |   |
|   |                       |                         |                             |   |
|   |  - Observes State     |       UI State (Flow)   |  - Holds StateFlow<State>   |   |
|   |  - Renders Layout     |<------------------------|  - Exposes Channel<Effect>  |   |
|   |  - Emits Intent       |                         |  - Processes Intent         |   |
|   +-----------+-----------+                         +--------------+--------------+   |
|               |                                                    ^                  |
|               | User Interaction (Intent)                          |                  |
|               +----------------------------------------------------+                  |
|                                                                    |                  |
|               Side Effects (Channel)                               |                  |
|               <----------------------------------------------------+                  |
+--------------------------------------------------------------------+------------------+
                                                                     |
                                                Invokes Use Case /   | Emits Data
                                                Executes Domain Logic| (Flow/Result)
                                                                     v
+--------------------------------------------------------------------+------------------+
|                                         DOMAIN                                        |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                           Use Cases / Interactors                             |   |
|   |  - Pure Business Rules (e.g., TransferFundsUseCase, GetUserProfileUseCase)    |   |
|   |  - No Android SDK Dependencies (Zero android.* imports)                       |   |
|   +---------------------------------------+---------------------------------------+   |
|                                           |                                           |
|                                           | Inversion of Control                      |
|                                           v (Calls Interface)                         |
|   +-------------------------------------------------------------------------------+   |
|   |                             Domain Repositories                               |   |
|   |  - Interfaces defined in Domain layer (e.g., UserRepository, WalletRepository)|   |
|   +-------------------------------------------------------------------------------+   |
+-------------------------------------------------------------------+-------------------+
                                                                    ^
                                                                    | Implements Interface
                                                                    | (Dependency Inversion)
+-------------------------------------------------------------------+-------------------+
|                                          DATA                                         |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                        Repository Implementations                             |   |
|   |  - UserRepositoryImpl, WalletRepositoryImpl                                   |   |
|   |  - Orchestrates Data Sources (Cache-First, Network-Bound Resource)            |   |
|   +-----------------------+-------------------------------+-----------------------+   |
|                           |                               |                           |
|                           v                               v                           |
|           +-------------------------------+   +-------------------------------+       |
|           |       Remote Data Source      |   |       Local Data Source       |       |
|           |  - Ktor / Retrofit            |   |  - Room DB / SQLDelight       |       |
|           |  - Network API Services       |   |  - DataStore Preferences      |       |
|           +-------------------------------+   +-------------------------------+       |
+---------------------------------------------------------------------------------------+
```

### Struktur Modul Gradle Skala Enterprise

```text
:app
 ├── dependsOn ──> :feature:transfer
 ├── dependsOn ──> :feature:auth
 └── dependsOn ──> :core:ui

:feature:transfer
 ├── dependsOn ──> :core:domain
 ├── dependsOn ──> :core:model
 ├── dependsOn ──> :core:ui
 └── NO ACCESS ──> :core:data (Pencegahan bocornya layer data ke UI)

:core:data
 ├── implements ─> :core:domain (Repository interfaces)
 ├── dependsOn ──> :core:model
 ├── dependsOn ──> :core:database
 └── dependsOn ──> :core:network

:core:domain
 ├── dependsOn ──> :core:model
 └── ZERO DEPENDENCIES on Android framework or other internal modules

:core:model
 └── PURE KOTLIN models (Shared entities)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Tiga Pilar MVI: Intent, State, Side-Effect

```text
                  +-----------------------------------+
                  |           UI Interaction          |
                  +-----------------+-----------------+
                                    |
                                    v
     +-------------------------------------------------------------+
     |                    UIIntent (User Action)                   |
     | sealed interface UIIntent {                                 |
     |   data class TransferRequested(...) : UIIntent              |
     |   data object RefreshClicked : UIIntent                     |
     | }                                                           |
     +------------------------------+------------------------------+
                                    |
                                    v
     +-------------------------------------------------------------+
     |                     Reducer / Processing                    |
     | CurrentState + UIIntent + Async Result => New UIState       |
     +------------------------------+------------------------------+
                                    |
                 +------------------+------------------+
                 |                                     |
                 v                                     v
+---------------------------------+   +---------------------------------+
|       UIState (LTS/Sticky)      |   |    UIEffect (STS/Transient)     |
|                                 |   |                                 |
| - Long-Term State               |   | - Short-Term State              |
| - Disimpan via StateFlow        |   | - Ditransmisikan via Channel    |
| - Bertahan saat rotasi layar    |   | - Konsumsi 1x (One-off)         |
| - Mewakili Canvas Visual        |   | - Navigasi, Toast, Dialog       |
+---------------------------------+   +---------------------------------+
```

### Mekanisme Internal Mutasi State: Concurrency Synchronization

Dalam lingkungan multithreading, dua coroutine yang memutasi state secara paralel dapat memicu *race condition*.

* **Pendekatan Buruk:** Membaca `_state.value`, lalu mengubahnya:
  ```kotlin
  // CRITICAL BUG: Rawan Race Condition!
  val current = _uiState.value
  _uiState.value = current.copy(isLoading = true)
  ```
  Jika dua *thread* mengeksekusi ini secara bersamaan, mutasi pertama akan tertimpa (*lost update*).

* **Solusi Idiomatik Coroutines:** Menggunakan `MutableStateFlow.update`:
  ```kotlin
  _uiState.update { currentState ->
      currentState.copy(isLoading = true)
  }
  ```
  Di balik layar, `update` menggunakan *Compare-And-Swap (CAS) atomic loop*:
  ```kotlin
  // Implementasi internal kotlinx.coroutines.flow.StateFlowKt
  public inline fun <T> MutableStateFlow<T>.update(function: (T) -> T) {
      while (true) {
          val prev = value
          val next = function(prev)
          if (compareAndSet(prev, next)) return
      }
  }
  ```
  Jika state berubah di antara waktu evaluasi `function(prev)` dan eksekusi `compareAndSet`, operasi gagal secara atomik dan loop mengulang evaluasi dengan state terbaru.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. The Clean Architecture Boundaries & DIP

Hukum utama Clean Architecture yang dirumuskan oleh Robert C. Martin menyatakan: **Dependensi kode sumber hanya boleh mengarah ke dalam (*Source code dependencies must point only inward, toward higher-level policies*)**.

* **Entities / Models:** Representasi objek bisnis murni.
* **Use Cases:** Mengorkestrasikan aliran data ke dan dari entitas. Tidak terikat pada platform Android (tidak boleh ada impor `android.content.Context`, `android.os.Bundle`, dsb).
* **Interface Adapters (ViewModel, Presenter, Repository Impl):** Mengonversi data dari format Use Case ke format GUI atau database.
* **Frameworks & Drivers (Compose, Room, Retrofit, Ktor):** Lapisan terluar yang paling sering berubah.

Berdasarkan *Dependency Inversion Principle* (DIP):
* Modul tingkat tinggi (`:core:domain`) tidak boleh bergantung pada modul tingkat rendah (`:core:data`).
* Keduanya harus bergantung pada abstraksi (antarmuka repositori di dalam `:core:domain`).
* Modul tingkat rendah mengimplementasikan abstraksi tersebut.

### 2. Stateflow vs SharedFlow vs Channel untuk Event Handling

Kesalahan arsitektural fatal yang kerap ditemui adalah menggunakan `SharedFlow` untuk memancarkan navigasi atau pesan *one-off error*.

| Komponen | Retensi / Replay | Kapasitas Buffer | Sifat Konsumsi | Skenario Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **`StateFlow`** | Selalu menyimpan 1 nilai terakhir (Konflasi otomatis). | 1 (Konflasi nilai baru jika tidak terkonsumsi). | Multicast (Banyak observer menerima data sama). | **UI State murni.** Representasi visual layar kapan saja. |
| **`SharedFlow`** | Dikonfigurasi via `replay` parameter ($0..n$). | Dikonfigurasi via `extraBufferCapacity`. | Multicast. Emisi tanpa observer akan di-*drop* jika buffer penuh / replay = 0. | **Broadcast Stream.** Contoh: Sinyal log out global, notifikasi *real-time*. |
| **`Channel`** | Tanpa replay default. Mengantre data hingga dikonsumsi. | Sesuai konfigurasi buffer (`RENDEZVOUS`, `BUFFERED`, `UNLIMITED`). | Unicast (Satu event dikonsumsi tepat oleh satu subscriber). | **Side-Effects.** Navigasi, Show Toast, Analytics Events. |

#### Mengapa SharedFlow(replay = 0) Berbahaya untuk Navigasi UI?
Jika ViewModel mengeksekusi navigasi melalui `MutableSharedFlow(replay = 0)` saat fragment/layar sedang berada di latar belakang (*stopped state*), pengamat Compose (`LaunchedEffect` atau lifecycle-aware flow collector) telah berhenti berlangganan (*inactive*). Event tersebut akan langsung dibuang ke kehampaan (*dropped*). Akibatnya, saat pengguna kembali ke aplikasi, aksi navigasi hilang permanen.

Menggunakan `Channel(capacity = Channel.BUFFERED)` yang diekspos sebagai Flow via `receiveAsFlow()` menjamin event diantrekan di memori sampai UI kembali aktif (*resumed*) untuk mengonsumsinya secara tepat satu kali (*guaranteed single-event consumption*).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah fondasi arsitektur MVI + Clean Architecture berbasis Kotlin murni dan Coroutines Flow.

### 1. Core Contract Abstraction

```kotlin
package com.enterprise.core.arch

import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.Flow

// Marker interface untuk State yang immutable
interface UiState

// Marker interface untuk Intent / Action dari UI
interface UiIntent

// Marker interface untuk Side Effect sekali pakai
interface UiEffect

// Kontrak dasar arsitektur untuk seluruh ViewModel
interface MviViewModel<S : UiState, in I : UiIntent, out E : UiEffect> {
    val uiState: StateFlow<S>
    val uiEffect: Flow<E>
    fun processIntent(intent: I)
}
```

### 2. Base MVI ViewModel Implementation

```kotlin
package com.enterprise.core.arch

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

abstract class BaseViewModel<S : UiState, I : UiIntent, E : UiEffect>(
    initialState: S
) : ViewModel(), MviViewModel<S, I, E> {

    private val _uiState = MutableStateFlow(initialState)
    override val uiState: StateFlow<S> = _uiState.asStateFlow()

    // Menggunakan Buffered Channel agar Side Effect tidak hilang saat UI paused
    private val _uiEffect = Channel<E>(capacity = Channel.BUFFERED)
    override val uiEffect: Flow<E> = _uiEffect.receiveAsFlow()

    override fun processIntent(intent: I) {
        handleIntent(intent)
    }

    protected abstract fun handleIntent(intent: I)

    // Helper aman untuk mutasi state internal
    protected fun updateState(reducer: (currentState: S) -> S) {
        _uiState.update(reducer)
    }

    // Mengirim side effect ke antrean UI
    protected fun sendEffect(effect: E) {
        viewModelScope.launch {
            _uiEffect.send(effect)
        }
    }
}
```

### 3. Use Case Pattern dengan Functional Error Handling

```kotlin
package com.enterprise.core.domain

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext

sealed interface DomainResult<out T> {
    data class Success<out T>(val data: T) : DomainResult<T>
    data class Failure(val error: DomainError) : DomainResult<Nothing>
}

sealed interface DomainError {
    data object NetworkTimeout : DomainError
    data object Unauthorized : DomainError
    data class BusinessLogicViolation(val message: String) : DomainError
    data class Unknown(val cause: Throwable) : DomainError
}

// Base UseCase eksekusi coroutine tunggal
abstract class SuspendUseCase<in Input, Output>(
    private val dispatcher: CoroutineDispatcher
) {
    suspend operator fun invoke(input: Input): DomainResult<Output> = withContext(dispatcher) {
        runCatching {
            execute(input)
        }.fold(
            onSuccess = { DomainResult.Success(it) },
            onFailure = { DomainResult.Failure(mapThrowable(it)) }
        )
    }

    protected abstract suspend fun execute(input: Input): Output

    protected open fun mapThrowable(throwable: Throwable): DomainError {
        return DomainError.Unknown(throwable)
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah arsitektur dasar pada Seksi 07:

1. **`interface UiState` & `interface UiIntent`**: Memberikan batasan tipe kompilasi (*compile-time type safety*). Mencegah pengembang mencampuradukkan kelas domain atau *event bus generic* ke dalam pipeline rendering.
2. **`private val _uiState = MutableStateFlow(initialState)`**: 
   * Encapsulation murni. State internal hanya boleh dimutasi di dalam cakupan kelas ViewModel.
   * `asStateFlow()` menyembunyikan fungsi mutasi (`value = ...`, `update { ... }`) dari lapisan UI. UI hanya memiliki akses baca (`read-only`).
3. **`Channel<E>(capacity = Channel.BUFFERED)`**:
   * Konfigurasi `Channel.BUFFERED` memberikan antrean transitif default (biasanya 64 item). Jika UI mengalami rotasi konfigurasi selama transisi, event tidak memblokir coroutine pemancar (*non-suspending emission under capacity*) dan tidak membuang data.
4. **`_uiEffect.receiveAsFlow()`**:
   * Mengonversi `Channel` menjadi `Flow` dingin (*cold Flow*) yang bertindak sebagai *unicast consumer*. Hanya ada satu observer yang dapat mengonsumsi paket `UiEffect` tersebut, menjamin idempotensi navigasi.
5. **`_uiState.update(reducer)`**:
   * Mengeksekusi mutasi berbasis fungsi murni. Fungsi `reducer` menerima state saat ini dan mengembalikan state baru.
   * Melindungi integritas state dari situasi *concurrency race condition* berkat implementasi internal *atomic CAS loop*.
6. **`suspend operator fun invoke(...) = withContext(dispatcher)`**:
   * Melakukan *dispatcher injection*. Menjamin use case selalu berjalan pada thread pool yang tepat (misalnya `Dispatchers.IO` atau `Dispatchers.Default`), bukan mengandalkan pemanggil (*caller-safety*).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Sistem Transfer Dana FinTech (Core Banking)

Sebuah bank digital memerlukan fitur transfer dana antar rekening dengan persyaratan rekayasa tingkat tinggi:

1. **Persyaratan Fungsional:**
   * Pengguna menginput nomor rekening target, nominal transfer, dan catatan opsional.
   * Validasi saldo lokal secara instan sebelum menembak API.
   * Eksekusi transfer membutuhkan autentikasi token biometrik dua langkah (2FA).
   * Menampilkan layar status transaksi: Loading -> Sukses / Gagal.

2. **Kondisi Ekstrem (Edge & Concurrency Cases):**
   * Pengguna menekan tombol "Kirim Sekarang" secara agresif (*double/triple tap*). Sistem harus kebal terhadap duplikasi transaksi (*Idempotency check*).
   * Gangguan sinyal internet di tengah proses eksekusi (timeout API). Saldo tidak boleh terpotong di UI sebelum konfirmasi mutlak dari server.
   * Layar diputar (*configuration change*) atau aplikasi masuk background saat mutasi berlangsung: Proses transfer tidak boleh dibatalkan di tengah jalan, dan UI harus menampilkan hasil akhir yang benar saat pengguna kembali membuka aplikasi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi end-to-end fitur transfer dana menggunakan arsitektur modular Clean Architecture + MVI.

### 1. Domain Layer (`:feature:transfer:domain`)

```kotlin
package com.enterprise.banking.transfer.domain.model

import java.math.BigDecimal

data class Account(
    val accountNumber: String,
    val accountHolderName: String,
    val balance: BigDecimal
)

data class TransferRequest(
    val recipientAccountNumber: String,
    val amount: BigDecimal,
    val idempotencyKey: String,
    val note: String?
)

data class TransferReceipt(
    val transactionId: String,
    val timestampMillis: Long,
    val remainingBalance: BigDecimal
)
```

```kotlin
package com.enterprise.banking.transfer.domain.repository

import com.enterprise.banking.transfer.domain.model.TransferReceipt
import com.enterprise.banking.transfer.domain.model.TransferRequest
import kotlinx.coroutines.flow.Flow

interface TransferRepository {
    suspend fun executeTransfer(request: TransferRequest): TransferReceipt
    fun getAccountBalance(): Flow<BigDecimal>
}
```

```kotlin
package com.enterprise.banking.transfer.domain.usecase

import com.enterprise.banking.transfer.domain.model.TransferReceipt
import com.enterprise.banking.transfer.domain.model.TransferRequest
import com.enterprise.banking.transfer.domain.repository.TransferRepository
import com.enterprise.core.domain.DomainError
import com.enterprise.core.domain.DomainResult
import com.enterprise.core.domain.SuspendUseCase
import kotlinx.coroutines.CoroutineDispatcher
import java.math.BigDecimal
import java.util.UUID

class ExecuteTransferUseCase(
    private val repository: TransferRepository,
    ioDispatcher: CoroutineDispatcher
) : SuspendUseCase<ExecuteTransferUseCase.Params, TransferReceipt>(ioDispatcher) {

    data class Params(
        val targetAccountNumber: String,
        val amount: BigDecimal,
        val note: String?
    )

    override suspend fun execute(input: Params): TransferReceipt {
        require(input.targetAccountNumber.isNotBlank()) { "Nomor rekening tujuan tidak boleh kosong." }
        require(input.amount > BigDecimal.ZERO) { "Nominal transfer harus lebih besar dari nol." }

        val request = TransferRequest(
            recipientAccountNumber = input.targetAccountNumber,
            amount = input.amount,
            idempotencyKey = UUID.randomUUID().toString(),
            note = input.note
        )

        return repository.executeTransfer(request)
    }

    override fun mapThrowable(throwable: Throwable): DomainError {
        return when (throwable) {
            is IllegalArgumentException -> DomainError.BusinessLogicViolation(throwable.message.orEmpty())
            is java.net.SocketTimeoutException -> DomainError.NetworkTimeout
            else -> super.mapThrowable(throwable)
        }
    }
}
```

### 2. Presentation Layer: Contracts (`:feature:transfer:ui`)

```kotlin
package com.enterprise.banking.transfer.ui

import androidx.compose.runtime.Immutable
import com.enterprise.banking.transfer.domain.model.TransferReceipt
import com.enterprise.core.arch.UiEffect
import com.enterprise.core.arch.UiIntent
import com.enterprise.core.arch.UiState
import java.math.BigDecimal

@Immutable
data class TransferUiState(
    val balance: BigDecimal = BigDecimal.ZERO,
    val recipientAccountNumber: String = "",
    val amountText: String = "",
    val note: String = "",
    val isTransferring: Boolean = false,
    val errorMessage: String? = null
) : UiState {
    val isTransferExecutable: Boolean
        get() = recipientAccountNumber.length >= 8 &&
                amountText.toBigDecimalOrNull()?.let { it > BigDecimal.ZERO && it <= balance } == true &&
                !isTransferring
}

sealed interface TransferUiIntent : UiIntent {
    data class AccountNumberChanged(val newNumber: String) : TransferUiIntent
    data class AmountChanged(val newAmount: String) : TransferUiIntent
    data class NoteChanged(val newNote: String) : TransferUiIntent
    data object SubmitTransfer : TransferUiIntent
    data object DismissError : TransferUiIntent
}

sealed interface TransferUiEffect : UiEffect {
    data class NavigateToReceipt(val receipt: TransferReceipt) : TransferUiEffect
    data class ShowToast(val message: String) : TransferUiEffect
    data object TriggerBiometricPrompt : TransferUiEffect
}
```

### 3. Presentation Layer: ViewModel Implementation

```kotlin
package com.enterprise.banking.transfer.ui

import androidx.lifecycle.viewModelScope
import com.enterprise.banking.transfer.domain.repository.TransferRepository
import com.enterprise.banking.transfer.domain.usecase.ExecuteTransferUseCase
import com.enterprise.core.arch.BaseViewModel
import com.enterprise.core.domain.DomainError
import com.enterprise.core.domain.DomainResult
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import java.math.BigDecimal

class TransferViewModel(
    private val executeTransferUseCase: ExecuteTransferUseCase,
    private val transferRepository: TransferRepository
) : BaseViewModel<TransferUiState, TransferUiIntent, TransferUiEffect>(TransferUiState()) {

    init {
        observeAccountBalance()
    }

    private fun observeAccountBalance() {
        transferRepository.getAccountBalance()
            .onEach { latestBalance ->
                updateState { it.copy(balance = latestBalance) }
            }
            .catch {
                sendEffect(TransferUiEffect.ShowToast("Gagal memuat saldo terbaru."))
            }
            .launchIn(viewModelScope)
    }

    override fun handleIntent(intent: TransferUiIntent) {
        when (intent) {
            is TransferUiIntent.AccountNumberChanged -> {
                updateState { it.copy(recipientAccountNumber = intent.newNumber) }
            }
            is TransferUiIntent.AmountChanged -> {
                updateState { it.copy(amountText = intent.newAmount) }
            }
            is TransferUiIntent.NoteChanged -> {
                updateState { it.copy(note = intent.newNote) }
            }
            is TransferUiIntent.DismissError -> {
                updateState { it.copy(errorMessage = null) }
            }
            TransferUiIntent.SubmitTransfer -> {
                initiateTransferFlow()
            }
        }
    }

    private fun initiateTransferFlow() {
        val currentState = uiState.value
        if (!currentState.isTransferExecutable) return

        // Memicu otentikasi biometrik sebelum eksekusi API
        sendEffect(TransferUiEffect.TriggerBiometricPrompt)
    }

    // Dipanggil UI setelah biometrik berhasil diverifikasi
    fun onBiometricAuthenticationSuccess() {
        val currentState = uiState.value
        val amount = currentState.amountText.toBigDecimalOrNull() ?: return

        updateState { it.copy(isTransferring = true, errorMessage = null) }

        viewModelScope.launch {
            val params = ExecuteTransferUseCase.Params(
                targetAccountNumber = currentState.recipientAccountNumber,
                amount = amount,
                note = currentState.note.takeIf { it.isNotBlank() }
            )

            when (val result = executeTransferUseCase(params)) {
                is DomainResult.Success -> {
                    updateState { it.copy(isTransferring = false) }
                    sendEffect(TransferUiEffect.NavigateToReceipt(result.data))
                }
                is DomainResult.Failure -> {
                    val message = when (val error = result.error) {
                        DomainError.NetworkTimeout -> "Koneksi terputus. Mohon periksa status mutasi transaksi Anda."
                        DomainError.Unauthorized -> "Sesi login kedaluwarsa. Silakan login kembali."
                        is DomainError.BusinessLogicViolation -> error.message
                        is DomainError.Unknown -> "Terjadi kesalahan internal: ${error.cause.localizedMessage}"
                    }
                    updateState { it.copy(isTransferring = false, errorMessage = message) }
                }
            }
        }
    }
}
```

### 4. UI Layer: Jetpack Compose Implementation

```kotlin
package com.enterprise.banking.transfer.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.flow.Flow

@Composable
fun TransferScreen(
    viewModel: TransferViewModel,
    onNavigateToReceipt: (String) -> Unit,
    onTriggerBiometrics: (() -> Unit) -> Unit,
    modifier: Modifier = Modifier
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    // Mengonsumsi UiEffect secara Lifecycle-Aware
    CollectSideEffect(flow = viewModel.uiEffect) { effect ->
        when (effect) {
            is TransferUiEffect.NavigateToReceipt -> {
                onNavigateToReceipt(effect.receipt.transactionId)
            }
            is TransferUiEffect.ShowToast -> {
                snackbarHostState.showSnackbar(effect.message)
            }
            TransferUiEffect.TriggerBiometricPrompt -> {
                onTriggerBiometrics {
                    viewModel.onBiometricAuthenticationSuccess()
                }
            }
        }
    }

    // Menampilkan error state jika ada
    LaunchedEffect(uiState.errorMessage) {
        uiState.errorMessage?.let { error ->
            snackbarHostState.showSnackbar(error)
            viewModel.processIntent(TransferUiIntent.DismissError)
        }
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { innerPadding ->
        TransferContent(
            state = uiState,
            onIntent = viewModel::processIntent,
            modifier = Modifier.padding(innerPadding)
        )
    }
}

@Composable
private fun TransferContent(
    state: TransferUiState,
    onIntent: (TransferUiIntent) -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = "Saldo Tersedia: Rp ${state.balance}",
                style = MaterialTheme.typography.titleMedium
            )

            Spacer(modifier = Modifier.height(16.dp))

            OutlinedTextField(
                value = state.recipientAccountNumber,
                onValueChange = { onIntent(TransferUiIntent.AccountNumberChanged(it)) },
                label = { Text("Nomor Rekening Tujuan") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.isTransferring
            )

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = state.amountText,
                onValueChange = { onIntent(TransferUiIntent.AmountChanged(it)) },
                label = { Text("Nominal Transfer") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.isTransferring
            )

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = state.note,
                onValueChange = { onIntent(TransferUiIntent.NoteChanged(it)) },
                label = { Text("Catatan (Opsional)") },
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.isTransferring
            )

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = { onIntent(TransferUiIntent.SubmitTransfer) },
                enabled = state.isTransferExecutable,
                modifier = Modifier.fillMaxWidth()