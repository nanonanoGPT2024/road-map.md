# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengonstruksi** arsitektur aplikasi Android skala enterprise berbasis *Clean Architecture* dan *Model-View-Intent* (MVI) dengan *Unidirectional Data Flow* (UDF).
- **Membongkar Mekanisme Internal** Jetpack Compose (Slot Table, Recomposer, Snapshot State System) serta lifecycle Coroutine/Flow guna mengeliminasi memory leak dan frame drop (< 16.6ms / 60-120 FPS).
- **Mengimplementasikan** manajemen dependensi multi-modul tingkat lanjut menggunakan Dagger/Hilt dengan custom scopes, subcomponents, dan dynamic feature injection.
- **Mengontrol Konkurensi & Sinkronisasi** data reaktif menggunakan Kotlin Coroutines primitives (Mutex, Actors, Channels) dan Flow backpressure strategy pada skenario offline-first.
- **Mendiagnosis & Mengoptimasi** performa aplikasi enterprise mencakup mitigasi ANR (Application Not Responding), profiling alokasi heap via Android Studio Profiler, serta optimasi R8/ProGuard.

---

## 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:
- **Kotlin Advanced**: Generics (reified, variance `in`/`out`), Higher-order functions, Kotlin Bytecode basics, Memory Model (Stack vs Heap alokasi referensi).
- **Android Core Runtime**: Activity/Fragment Lifecycle, Binder IPC, Main/UI Thread Looper & Handler.
- **Environment & Tooling**:
  - Android Studio Iguana / Jellyfish (atau versi lebih tinggi).
  - Kotlin 1.9.20+ / 2.0.0+.
  - Gradle Version Catalog (`libs.versions.toml`) dengan AGP 8.3+.
  - JDK 17 LTS.

---

## 3. Concept & Internal Architecture

Arsitektur sistem Android enterprise modern beroperasi di atas koordinasi antara Linux Kernel, Android Runtime (ART), dan application runtime layer. Memahami abstraksi framework memerlukan pemahaman pada level eksekusi instruksi dan alokasi memori.

```
+-------------------------------------------------------------------------------+
|                       UI Layer (Jetpack Compose / MVI)                        |
|   +-----------------------+                 +-----------------------------+   |
|   |   UI State (Immutable)| <============== | Intent/Action (User Events) |   |
|   +-----------------------+                 +-----------------------------+   |
|              ^                                             |                  |
+--------------|---------------------------------------------|------------------+
               | (StateFlow Emit)                            | (Process Intent)
+--------------|---------------------------------------------v------------------+
|              |               Domain Layer                                     |
|   +-----------------------------------------------------------------------+   |
|   |   Use Cases / Interactors (Pure Kotlin, Coroutine Context: Dispatchers) |   |
|   +-----------------------------------------------------------------------+   |
+---------------------------------------------|---------------------------------+
                                              | (Repository Interface)
+---------------------------------------------v---------------------------------+
|                                Data Layer                                     |
|   +-------------------------------------+   |   +-------------------------+   |
|   |   Local Data Source (Room / SQLite) | <-+-> |   Remote (Ktor / Retrofit)| |
|   +-------------------------------------+       +-------------------------+   |
+-------------------------------------------------------------------------------+
```

### 3.1. Compose Runtime: Slot Table & Snapshot State System

Jetpack Compose tidak memanipulasi pohon `View` Android hierarkis (`android.view.View`). Compose runtime menggunakan struktur data **Gap Buffer** yang disebut **Slot Table**.

- **Slot Table**: Memori linear berupa array datar yang menyimpan data composer secara sekuensial. Ketika UI direkonstruksi (*Recomposition*), pointer slot table membaca grup node. Jika terdapat node yang berubah (berdasarkan komparasi struktural referensi `State<T>`), gap pointer dipindahkan ke posisi target untuk melakukan *in-place mutation*, penyisipan, atau penghapusan tanpa memicu realokasi pohon memori yang masif.
- **Snapshot State Tracking**: Sistem snapshot (`androidx.compose.runtime.snapshots.Snapshot`) menggunakan model MVCC (*Multi-Version Concurrency Control*). Ketika nilai `mutableStateOf` dibaca di dalam blok composable, runtime mendaftarkan observer ke thread-local snapshot aktif. Ketika mutasi state terjadi (`Snapshot.sendApplyNotifications()`), Composer menandai composable scope tersebut sebagai *invalidated*, yang kemudian menjadwalkan pass recomposition pada frame `Choreographer` berikutnya.

```
Compose Slot Table Architecture:
Array:  [GroupNode][Data: Text][Data: Color][ GAP / RESERVED SPACE ][GroupNode]
Pointer:   ^                                        ^                   ^
       Current Read                            Insert/Delete       Next Subtree
```

### 3.2. Kotlin Coroutines & Structured Concurrency Internals

Kotlin Coroutines bukan thread virtual murni level kernel, melainkan mesin automata status (*State Machine*) kooperatif berbasis *Continuation Passing Style* (CPS).

1. **Transformasi CPS**: Kompilator Kotlin membongkar fungsi `suspend` menjadi fungsi biasa yang menerima parameter implisit `Continuation<T>`. Di dalamnya, dibuat subclass `CoroutineImpl` dengan fungsi `invokeSuspend()` yang berisi blok `switch-case` (`when (label)`).
2. **Suspension Point**: Ketika mencapai fungsi non-blocking I/O atau penundaan (`delay`, database query), eksekusi tidak memblokir kernel thread OS worker. State lokal (local variable registers) disimpan ke dalam field objek `Continuation`, dan callback didaftarkan ke runtime handler/event loop.
3. **Structured Concurrency**: Mengaitkan hierarki eksekusi melalui objek `Job`. Pembatalan (*cancellation*) pada root `Job` akan mentransmisikan sinyal kooperatif `CancellationException` ke seluruh rantai child coroutines secara rekursif melalui tree traversal.

### 3.3. Dependency Injection Graph: Hilt/Dagger 2 Generation

Dagger 2/Hilt tidak menggunakan runtime reflection (seperti Spring framework standar). Semuanya divalidasi dan di-generate saat kompilasi (*Compile-time Annotation Processing / KSP*):

- **Kompilasi**: Kompilator memetakan dependensi melalui graf terarah asiklik (*Directed Acyclic Graph* - DAG).
- **Factories & Providers**: Setiap kelas beranotasi `@Inject` menghasilkan kelas `*_Factory.java` yang mengimplementasikan interface `Provider<T>`.
- **Component Hierarchy**: Hilt membungkus DAG ke dalam lifecycle komponen Android secara deterministik (`SingletonComponent` -> `ActivityRetainedComponent` -> `ViewModelComponent` -> `ActivityComponent` -> `FragmentComponent`). Alokasi instance scoped di-cache di dalam map array berukuran tetap yang terikat pada host lifecycle object.

---

## 4. Why & What

| Pendekatan Legacy (MVC/MVP/Clean Architecture Standar) | Arsitektur Enterprise Modern (Clean + MVI + Reactive Engine) |
| :--- | :--- |
| **Mutable State Propagation**: State tersebar di banyak observer (`LiveData`, field lokal `Activity`), memicu *Race Conditions* inkonsistensi UI. | **Single Source of Truth (SSOT)**: State dibungkus immutable data class tunggal, dimutasi deterministik via state machine atau reducer. |
| **Fat ViewModel / God Object**: ViewModel menangani parsing API, database mapping, logika navigasi, dan update UI. | **Separation of Concerns Modular**: ViewModel murni memetakan UI Intent menjadi Business Use Case dan memancarkan immutable view state. |
| **Monolithic Single-Module**: Seluruh kode berada dalam module `:app`. Build time eksponensial seiring bertambahnya ratusan ribu baris kode. | **Fine-Grained Multi-Module**: Graph modul modular (`:core:network`, `:core:database`, `:feature:payment:domain`), caching build agresif via Gradle Build Cache. |
| **Blocking / Fragile Asynchrony**: Threading via RxJava chains tanpa lifecycle scope yang ketat, sering menyebabkan *Subscriber Leaks* saat Activity destroy. | **Lifecycle-Aware Coroutines**: Flow dikoleksi menggunakan operator aware lifecycle (`repeatOnLifecycle`), menghentikan upstream job seketika saat UI di latar belakang. |

### Anti-Patterns yang Dimusnahkan
1. **Multiple Single-Event Anti-Pattern**: Menggunakan `LiveData<Event<T>>` terpisah-pisah untuk navigasi, toast, dialog, yang memicu *event-dropping* saat konfigurasi perangkat berubah (rotasi layar).
2. **Leaky Coroutine Context**: Menggunakan `GlobalScope` yang membuat alokasi objek coroutine tetap hidup di root memory space meski layar sudah ditutup.

---

## 5. How (Workflow Detail)

Alur kerja arsitektural MVI dengan UDF pada ekosistem enterprise:

```
[User Action: Tap Button]
          |
          v
[Jetpack Compose Composable UI]
          |
          |  (1) Triggers Intent: e.g., SubmitOrderIntent
          v
[ViewModel (State Container)]
          |
          |  (2) Executes Use Case in Dispatchers.Default
          v
[Domain Layer: Interactor / Use Case]
          |
          |  (3) Queries Repository (Dispatches to IO)
          v
[Data Layer: Repository Implementation]
    +-----+---------------------------------------+
    |                                             |
    v (Network Fetch)                             v (Local Cache Fallback)
[Remote DataSource (Ktor)]              [Local DataSource (Room)]
    |                                             |
    +---------------------+-----------------------+
                          |
                          v
          (4) Maps Entity to Domain Model
                          |
                          v
        [Returns Flow<Result<T>> to Use Case]
                          |
                          v
            [Emits Result to ViewModel]
                          |
                          v
[ViewModel Reducer: Computes New Immutable State]
                          |
                          |  (5) StateFlow.value = NewState
                          v
[Composable: Collects State via collectAsStateWithLifecycle]
                          |
                          v
[Compose Runtime: Slot Table Invalidation & Recomposition]
```

1. **User Action**: Interaksi pengguna memicu eksekusi event closure, meneruskan *Intent* terdefinisi (sealed interface) ke ViewModel.
2. **Processing Intent**: ViewModel menerima intent melalui handler fungsi publik, mengeksekusi operasi asinkron yang dibatasi oleh `viewModelScope`.
3. **Domain Interactor Execution**: Use Case mengeksekusi aturan bisnis independen (validasi, perhitungan), memanggil satu atau lebih repository.
4. **Data Aggregation**: Repository mengoordinasikan *caching strategy* (misal: *network-bound resource*), mentransformasi DTO (*Data Transfer Object*) jaringan atau entity database menjadi domain entity murni.
5. **Deterministic State Transition**: ViewModel menerima hasil, me-reduce status lama dengan data baru menjadi salinan `State` yang baru secara atomik, lalu memancarkannya ke `StateFlow`.
6. **Reactive Recomposition**: UI layer mengoleksi `StateFlow` melalui `collectAsStateWithLifecycle()`, memicu evaluasi recomposition hanya pada nodus Compose yang membaca properti yang berubah secara presisi.

---

## 6. Analogy & Diagram ASCII

### Analogi: Jalur Perakitan Pabrik Modern (Smart Assembly Line)
Bayangkan arsitektur aplikasi ini seperti jalur perakitan otomotif:
- **UI (Compose)**: Papan display visual yang menampilkan status mobil di stasiun perakitan. Papan ini tidak membuat mobil, ia hanya membaca sensor.
- **Intent**: Tombol yang ditekan oleh teknisi perakitan ("Pasang Pintu").
- **ViewModel (Supervisor)**: Menerima sinyal tombol, mencocokkannya dengan alur perakitan, dan memberikan perintah ke robot mekanik.
- **Use Case (Robot Spesifik)**: Robot khusus yang hanya tahu cara mengelas pintu dengan standar toleransi tertentu.
- **Repository (Gudang Suku Cadang)**: Menyediakan pintu. Gudang mengecek apakah stok lokal tersedia. Jika tidak, ia memesan langsung dari supplier pusat via ekspedisi (Network).
- **Slot Table (Slot Cetakan Fisik)**: Cetakan rangka tempat bagian-bagian dipasang secara modular. Jika cat tidak berubah, cetakan cat dilewati; hanya sekrup pintu yang diputar.

### Diagram: Multi-Module Dependency Architecture
Untuk menjamin skalabilitas, dependencies diarahkan ke dalam (*Inversion of Control*), mengisolasi feature dari feature lainnya:

```
                      +-------------------+
                      |      :app         | (Application Entry Point)
                      +-------------------+
                        /        |        \
                       v         v         v
           +-------------+ +-------------+ +-------------+
           | :feature:A  | | :feature:B  | | :feature:C  | (Feature Modules)
           +-------------+ +-------------+ +-------------+
                 \               |               /
                  v              v              v
           +---------------------------------------------+
           |               :core:domain                  | (Business Models & Interfaces)
           +---------------------------------------------+
                   ^                             ^
                   |                             |
     +---------------------------+ +-----------------------------+
     |        :core:data         | |        :core:network        | (Implementation & Infra)
     +---------------------------+ +-----------------------------+
                   \                             /
                    v                           v
           +---------------------------------------------+
           |               :core:database                | (Local Persistence)
           +---------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Core Concepts MVI & Flow
Implementasi MVI murni tanpa framework eksternal untuk memahami pola state stream.

```kotlin
// 1. Immutable State
data class CounterState(
    val count: Int = 0,
    val isLoading: Boolean = false
)

// 2. Sealed Intents
sealed interface CounterIntent {
    data object Increment : CounterIntent
    data object Decrement : CounterIntent
    data class SetCustom(val value: Int) : CounterIntent
}

// 3. Lightweight State Machine (ViewModel Pattern)
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class SimpleMviStateMachine {
    private val _state = MutableStateFlow(CounterState())
    val state: StateFlow<CounterState> = _state.asStateFlow()

    fun processIntent(intent: CounterIntent) {
        when (intent) {
            is CounterIntent.Increment -> {
                _state.update { it.copy(count = it.count + 1) }
            }
            is CounterIntent.Decrement -> {
                _state.update { it.copy(count = it.count - 1) }
            }
            is CounterIntent.SetCustom -> {
                _state.update { it.copy(count = intent.value) }
            }
        }
    }
}
```

---

### 7.2. Practical Example: Enterprise Production-Ready MVI Implementation
Contoh implementasi dunia nyata dengan: Clean Architecture, Multi-Module separation simulation, Jetpack Compose, Kotlin Coroutines Flow, Mutex-guarded operations, dan dependency injection Hilt.

#### Layer: Domain (`:core:domain`)
```kotlin
package com.enterprise.core.domain.model

data class Transaction(
    val id: String,
    val amount: Long,
    val currency: String,
    val timestamp: Long
)

sealed interface DomainResult<out T> {
    data class Success<T>(val data: T) : DomainResult<T>
    data class Failure(val error: AppError) : DomainResult<Nothing>
}

sealed class AppError(val message: String) {
    data object NetworkTimeout : AppError("Koneksi jaringan terputus.")
    data class ServerError(val code: Int, val desc: String) : AppError("Server error $code: $desc")
    data class Unknown(val throwable: Throwable) : AppError(throwable.localizedMessage ?: "Kesalahan fatal tak terduga")
}
```

```kotlin
package com.enterprise.core.domain.repository

import com.enterprise.core.domain.model.DomainResult
import com.enterprise.core.domain.model.Transaction
import kotlinx.coroutines.flow.Flow

interface TransactionRepository {
    fun observeTransactions(): Flow<List<Transaction>>
    suspend fun executeTransfer(targetAccountId: String, amount: Long): DomainResult<Transaction>
}
```

```kotlin
package com.enterprise.core.domain.usecase

import com.enterprise.core.domain.model.DomainResult
import com.enterprise.core.domain.model.Transaction
import com.enterprise.core.domain.repository.TransactionRepository
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext
import javax.inject.Inject

class ExecuteTransferUseCase @Inject constructor(
    private val repository: TransactionRepository,
    private val ioDispatcher: CoroutineDispatcher
) {
    suspend operator fun invoke(targetAccountId: String, amount: Long): DomainResult<Transaction> {
        // Business Rule: Transfer minimal Rp 10.000
        if (amount < 10_000L) {
            return DomainResult.Failure(
                com.enterprise.core.domain.model.AppError.ServerError(
                    code = 400,
                    desc = "Nominal transfer minimum adalah Rp 10.000"
                )
            )
        }
        return withContext(ioDispatcher) {
            repository.executeTransfer(targetAccountId, amount)
        }
    }
}
```

#### Layer: Data (`:core:data`)
```kotlin
package com.enterprise.core.data.repository

import com.enterprise.core.domain.model.AppError
import com.enterprise.core.domain.model.DomainResult
import com.enterprise.core.domain.model.Transaction
import com.enterprise.core.domain.repository.TransactionRepository
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.IOException
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ProductionTransactionRepository @Inject constructor() : TransactionRepository {

    // Thread-safety control untuk mutasi in-memory cache/local sync
    private val mutex = Mutex()
    private val transactionMemoryStore = mutableListOf<Transaction>()

    private val _transactionFlow = MutableSharedFlow<List<Transaction>>(
        replay = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )

    init {
        // Inisialisasi initial stream
        _transactionFlow.tryEmit(emptyList())
    }

    override fun observeTransactions(): Flow<List<Transaction>> = _transactionFlow.asSharedFlow()

    override suspend fun executeTransfer(
        targetAccountId: String,
        amount: Long
    ): DomainResult<Transaction> {
        return try {
            // Simulasi RPC / API Call
            // Thread blocking I/O simulated via network layer
            val response = fakeRemoteNetworkCall(targetAccountId, amount)

            mutex.withLock {
                transactionMemoryStore.add(0, response)
                _transactionFlow.emit(transactionMemoryStore.toList())
            }

            DomainResult.Success(response)
        } catch (e: IOException) {
            DomainResult.Failure(AppError.NetworkTimeout)
        } catch (t: Throwable) {
            DomainResult.Failure(AppError.Unknown(t))
        }
    }

    private suspend fun fakeRemoteNetworkCall(targetAccountId: String, amount: Long): Transaction {
        kotlinx.coroutines.delay(800) // Latency simulasi
        return Transaction(
            id = UUID.randomUUID().toString(),
            amount = amount,
            currency = "IDR",
            timestamp = System.currentTimeMillis()
        )
    }
}
```

#### Layer: Presentation (`:feature:wallet`)
```kotlin
package com.enterprise.feature.wallet.mvi

import com.enterprise.core.domain.model.Transaction

// 1. Immutable UI State
data class WalletUiState(
    val balance: Long = 50_000_000L,
    val transactions: List<Transaction> = emptyList(),
    val isTransferring: Boolean = false,
    val errorMessage: String? = null
)

// 2. User Actions (Intents)
sealed interface WalletIntent {
    data class InitiateTransfer(val targetAccountId: String, val amount: Long) : WalletIntent
    data object ClearError : WalletIntent
    data object RefreshTransactions : WalletIntent
}

// 3. Side Effects (One-off events like Navigation / Dialog)
sealed interface WalletSideEffect {
    data class ShowToast(val message: String) : WalletSideEffect
    data class NavigateToReceipt(val transactionId: String) : WalletSideEffect
}
```

```kotlin
package com.enterprise.feature.wallet

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.enterprise.core.domain.model.DomainResult
import com.enterprise.core.domain.repository.TransactionRepository
import com.enterprise.core.domain.usecase.ExecuteTransferUseCase
import com.enterprise.feature.wallet.mvi.WalletIntent
import com.enterprise.feature.wallet.mvi.WalletSideEffect
import com.enterprise.feature.wallet.mvi.WalletUiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class WalletViewModel @Inject constructor(
    private val executeTransferUseCase: ExecuteTransferUseCase,
    private val transactionRepository: TransactionRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(WalletUiState())
    val uiState: StateFlow<WalletUiState> = _uiState.asStateFlow()

    // Side-effects channel (buffer capacity guarantees no event dropping)
    private val _sideEffects = Channel<WalletSideEffect>(capacity = Channel.BUFFERED)
    val sideEffects = _sideEffects.receiveAsFlow()

    init {
        observeTransactionHistory()
    }

    private fun observeTransactionHistory() {
        viewModelScope.launch {
            transactionRepository.observeTransactions().collectLatest { txList ->
                _uiState.update { it.copy(transactions = txList) }
            }
        }
    }

    fun sendIntent(intent: WalletIntent) {
        when (intent) {
            is WalletIntent.InitiateTransfer -> handleTransfer(intent.targetAccountId, intent.amount)
            is WalletIntent.ClearError -> _uiState.update { it.copy(errorMessage = null) }
            is WalletIntent.RefreshTransactions -> observeTransactionHistory()
        }
    }

    private fun handleTransfer(targetAccountId: String, amount: Long) {
        if (_uiState.value.isTransferring) return // Atomic guard flag

        _uiState.update { it.copy(isTransferring = true, errorMessage = null) }

        viewModelScope.launch {
            when (val result = executeTransferUseCase(targetAccountId, amount)) {
                is DomainResult.Success -> {
                    _uiState.update {
                        it.copy(
                            balance = it.balance - result.data.amount,
                            isTransferring = false
                        )
                    }
                    _sideEffects.send(WalletSideEffect.NavigateToReceipt(result.data.id))
                }
                is DomainResult.Failure -> {
                    _uiState.update {
                        it.copy(
                            isTransferring = false,
                            errorMessage = result.error.message
                        )
                    }
                    _sideEffects.send(WalletSideEffect.ShowToast(result.error.message))
                }
            }
        }
    }
}
```

```kotlin
package com.enterprise.feature.wallet.ui

import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.enterprise.core.domain.model.Transaction
import com.enterprise.feature.wallet.WalletViewModel
import com.enterprise.feature.wallet.mvi.WalletIntent
import com.enterprise.feature.wallet.mvi.WalletSideEffect
import com.enterprise.feature.wallet.mvi.WalletUiState
import kotlinx.coroutines.flow.collectLatest

@Composable
fun WalletScreen(
    viewModel: WalletViewModel,
    onNavigateToReceipt: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    // Lifecycle-aware collection: safe across configuration change, pause, and stop
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    // Handle Side Effects safely in Composable Lifecycle
    LaunchedEffect(viewModel.sideEffects) {
        viewModel.sideEffects.collectLatest { effect ->
            when (effect) {
                is WalletSideEffect.ShowToast -> {
                    Toast.makeText(context, effect.message, Toast.LENGTH_SHORT).show()
                }
                is WalletSideEffect.NavigateToReceipt -> {
                    onNavigateToReceipt(effect.transactionId)
                }
            }
        }
    }

    WalletScreenContent(
        state = state,
        onSendTransfer = { target, amount ->
            viewModel.sendIntent(WalletIntent.InitiateTransfer(target, amount))
        },
        modifier = modifier
    )
}

@Composable
fun WalletScreenContent(
    state: WalletUiState,
    onSendTransfer: (String, Long) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Total Saldo: Rp ${state.balance}",
            style = MaterialTheme.typography.headlineMedium
        )

        Spacer(modifier = Modifier.height(16.dp))

        if (state.isTransferring) {
            CircularProgressIndicator(modifier = Modifier.align(Alignment.CenterHorizontally))
        } else {
            Button(
                onClick = { onSendTransfer("ACC-ID-9921", 50_000L) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Transfer Rp 50.000 ke ACC-ID-9921")
            }
        }

        state.errorMessage?.let { error ->
            Text(
                text = error,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(vertical = 8.dp)
            )
        }

        Spacer(modifier = Modifier.height(24.dp))
        Text(text = "Histori Transaksi", style = MaterialTheme.typography.titleMedium)

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(vertical = 8.dp)
        ) {
            items(
                items = state.transactions,
                key = { transaction -> transaction.id } // Stable Identity: Mencegah Recomposition berlebih
            ) { tx ->
                TransactionRowItem(item = tx)
            }
        }
    }
}

@Composable
private fun TransactionRowItem(item: Transaction) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = item.id.take(8))
            Text(text = "- Rp ${item.amount}", color = MaterialTheme.colorScheme.primary)
        }
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Financial Ride-Hailing App (Driver Ticker & Live Location Tracking)
- **Kondisi Beban**: 500.000 driver aktif mengirimkan lokasi per 500ms via WebSocket/MQTT. UI harus memperbarui rute pada Map Layer, menghitung surge-pricing, dan meng-update balance tanpa freeze.
- **Masalah Produksi**:
  1. *Frame Skipping*: Frekuensi update data dari background thread (500ms per packet) memicu recomposition masif pada seluruh screen root Compose.
  2. *Backpressure Buffer Overflow*: Ketika driver melewati area *tunnel* / jaringan lemah, WebSocket mengumpulkan ratusan frame posisi. Begitu koneksi pulih, terjadi *burst-emission* yang menyebabkan alokasi memori GC melonjak mendadak, berujung pada Out-Of-Memory (OOM) dan ANR 5 detik.

### Root Cause Analysis (RCA)
- Recomposition memvalidasi layout subtree karena state UI menyatukan `LocationState` dengan `AccountState`. Mutasi lat/long memicu re-evaluasi teks profil driver.
- Flow emisi data remote menggunakan `Channel` dengan strategi buffer `UNLIMITED`, sehingga alokasi memori meledak saat stream terhambat (*consumer slower than producer*).

### Implementasi Solusi Enterprise
1. **Dekomposisi State Granular & `@Stable` Annotations**: Memecah `DriverDashboardState` menjadi beberapa model kecil independen yang ditandai `@Immutable` / `@Stable` guna membantu compiler melakukan recomposition skipping.
2. **Backpressure Conflation**: Menerapkan operator `.conflate()` atau `.debounce(300L)` pada GPS Stream. Posisi lama yang belum sempat dirender dibuang (*dropped*), mempertahankan hanya snapshot koordinat teranyar.
3. **Penyelarasan Slot Table & Explicit Keys**: Memberikan identifier unik pada seluruh dynamic list items.

```kotlin
// Production Mitigation Snippet
@Stable
data class DriverLocation(val latitude: Double, val longitude: Double)

class LocationStreamProcessor @Inject constructor() {
    fun processHighFrequencyLocation(rawStream: Flow<DriverLocation>): Flow<DriverLocation> {
        return rawStream
            .conflate() // Hanya pertahankan koordinat paling baru saat consumer sibuk
            .flowOn(Dispatchers.Default) // Hindari parsing komputasi di Dispatchers.Main
    }
}
```

---

## 9. Trade-offs

| Dimensi Arsitektur | Pilihan A: MVI Penuh (Single State, Reducer, UDF) | Pilihan B: MVVM Tradisional (Multiple StateFlow/LiveData) |
| :--- | :--- | :--- |
| **Performance (CPU/Memory)** | Sedikit overhead pada alokasi memori akibat copy objek data state (`.copy()`), memerlukan mitigasi `@Stable`. | Alokasi memori lebih rendah per field; namun rawan *inconsistent UI states* karena multiple updates. |
| **Latency Render UI** | Sangat terprediksi. State perubahan diverifikasi secara terpusat oleh compiler Compose via referential equality. | Berisiko *multiple render cycles* dalam satu frame jika 3-4 LiveData berbeda memancarkan nilai bersamaan. |
| **Scalability (Team & Codebase)**| Sangat tinggi. Debugging berbasis *Time-Travel Debugging* & Event Replay; pengujian Use Case sepenuhnya terisolasi. | Menengah-Rendah. Ketika logika makin kompleks, ViewModel sulit dipetakan karena mutasi state terjadi di berbagai arah. |
| **Cost & Overhead Development** | *Boilerplate* tinggi: perlu membuat Intent, State, Reducer, Use Case, dan DTO mapping untuk tiap fitur. | Cepat dibangun di fase awal (MVP), namun *maintenance cost* membengkak seiring bertambahnya kompleksitas. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal Mengoleksi Flow pada Jetpack Compose
- **Gejala**: Aplikasi terus mengonsumsi data API/Location di latar belakang meski aplikasi di-*minimize*, menyebabkan baterai boros dan crash akibat mutasi state di background.
- **Penyebab**: Menggunakan `lifecycleScope.launch { flow.collect() }` atau `collectAsState()` biasa di dalam Composable. Objek Coroutine tetap berjalan aktif meskipun Activity berstatus `STOPPED`.
- **Solusi**: Gunakan API resmi Lifecycle 2.6+: `collectAsStateWithLifecycle()` yang otomatis pause/resume stream sesuai siklus hidup UI target (`Lifecycle.State.STARTED`).

```kotlin
// SALAH (Anti-Pattern)
val state by viewModel.uiState.collectAsState()

// BENAR (Production Level)
val state by viewModel.uiState.collectAsStateWithLifecycle()
```

### 10.2. State Invalidation Storm (Unstable Parameters)
- **Gejala**: Profiler menunjukkan Compose Layout mengalami recomposition berulang-ulang tanpa interaksi pengguna (*Frame rate anjlok* dari 120 FPS ke 20 FPS).
- **Penyebab**: Memasukkan tipe data koleksi standar seperti `List<T>`, `Set<T>`, atau objek non-annotated library eksternal ke dalam data class UI State. Kompilator Compose menganggap interface `List` sebagai *unstable* karena implementasi konkretnya bisa berupa `ArrayList` yang mutable.
- **Solusi**: Bungkus koleksi menggunakan Kotlinx Immutable Collections (`ImmutableList<T>`) atau berikan anotasi `@Immutable` / `@Stable` secara eksplisit pada model presentation.

```kotlin
// SALAH
data class ProductUiState(val items: List<Product>)

// BENAR
import kotlinx.collections.immutable.ImmutableList

@Immutable
data class ProductUiState(val items: ImmutableList<Product>)
```

### 10.3. Coroutine Exception Handling Swallow
- **Gejala**: Aplikasi crash seketika tanpa logs yang informatif, atau sebaliknya: loading indicator berputar selamanya tanpa error display.
- **Penyebab**: Membungkus blok `launch` dengan `try-catch` standar pada level root coroutine. `CancellationException` tertangkap (*swallowed*), merusak hierarki pembatalan coroutine parent-child.
- **Solusi**: Re-throw `CancellationException` secara eksplisit pada blok penanganan error.

```kotlin
// SALAH
try {
    fetchApi()
} catch (e: Exception) {
    _state.update { it.copy(loading = false) } // Mematikan mekanisme cooperational cancellation!
}

// BENAR
try {
    fetchApi()
} catch (e: Exception) {
    if (e is CancellationException) throw e
    _state.update { it.copy(loading = false, error = e.localizedMessage) }
}
```

---

## 11. Best Practices (Production Checklist)

Gunakan daftar checklist ini sebagai audit teknis sebelum melakukan merge ke branch `main`:

- [ ] **State Immutability**: Seluruh properti dalam UI State dideklarasikan sebagai `val` tanpa variabel mutable (`var`) internal.
- [ ] **Compose Key Optimization**: Seluruh iterasi dinamis (`LazyColumn`, `LazyRow`) wajib memiliki parameter `key = { it.stableId }`.
- [ ] **Coroutine Context Isolation**: Operasi I/O berat (Database, Retrofit/Ktor, File IO) secara ketat dibatasi di `Dispatchers.IO`; komputasi berat (JSON Parsing masif, image processing) berada di `Dispatchers.Default`.
- [ ] **Dependency Injection Scoping**: Hindari meletakkan `@Singleton` pada kelas yang memiliki state transien fitur. Gunakan `@ActivityRetainedScoped` atau `@ViewModelScoped`.
- [ ] **R8 Shrinking & Obfuscation**: Modul data memiliki aturan `@Keep` atau `@Serializable` yang valid pada file ProGuard (`proguard-rules.pro`) untuk mencegah reflection mapping failure saat APK di-minify:
  ```proguard
  -keepclassmembers class * {
      @com.google.gson.annotations.SerializedName <fields>;
  }
  ```
- [ ] **LeakCanary Integration**: Pastikan build type `debug` memasang LeakCanary untuk memonitor kebocoran referensi Activity/Fragment context secara otomatis.
- [ ] **Strict Concurrency Control**: Mutasi data di dalam local cache in-memory dikawal menggunakan Kotlin Coroutine `Mutex` untuk mencegah race condition antar worker thread.

---

## 12. Hands-on Practice

Panduan implementasi hands-on terstruktur untuk menguji pemahaman. Seluruh artefak proyek disimpan pada direktori: `hands-on/m02/`.

### Struktur Direktori Target
```text
hands-on/m02/
├── build.gradle.kts
├── settings.gradle.kts
└── src/
    └── main/
        └── java/com/enterprise/m02/
            ├── data/
            │   └── DefaultCryptoRepository.kt
            ├── domain/
            │   ├── CryptoModel.kt
            │   └── GetCryptoPriceUseCase.kt
            ├── presentation/
            │   ├── CryptoScreen.kt
            │   └── CryptoViewModel.kt
            └── MainActivity.kt
```

### Langkah 1: Siapkan Konfigurasi Gradle
Buat file `hands-on/m02/build.gradle.kts`:
```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.kapt)
    alias(libs.plugins.hilt.android)
}

android {
    namespace = "com.enterprise.m02"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.enterprise.m02"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.hilt.android)
    kapt(libs.hilt.compiler)
    implementation(libs.kotlinx.coroutines.android)
}
```

### Langkah 2: Domain Layer
Buat file `hands-on/m02/src/main/java/com/enterprise/m02/domain/CryptoModel.kt`:
```kotlin
package com.enterprise.m02.domain

data class CryptoAsset(
    val symbol: String,
    val priceUsd: Double,
    val lastUpdated: Long
)

interface CryptoRepository {
    suspend fun getRealtimePrice(symbol: String): Result<CryptoAsset>
}
```

Buat file `hands-on/m02/src/main/java/com/enterprise/m02/domain/GetCryptoPriceUseCase.kt`:
```kotlin
package com.enterprise.m02.domain

import javax.inject.Inject

class GetCryptoPriceUseCase @Inject constructor(
    private val repository: CryptoRepository
) {
    suspend operator fun invoke(symbol: String): Result<CryptoAsset> {
        val sanitized = symbol.trim().uppercase()
        if (sanitized.isBlank()) {
            return Result.failure(IllegalArgumentException("Simbol aset kripto tidak boleh kosong"))
        }
        return repository.getRealtimePrice(sanitized)
    }
}
```

### Langkah 3: Data Layer
Buat file `hands-on/m02/src/main/java/com/enterprise/m02/data/DefaultCryptoRepository.kt`:
```kotlin
package com.enterprise.m02.data

import com.enterprise.m02.domain.CryptoAsset
import com.enterprise.m02.domain.CryptoRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.random.Random

@Singleton
class DefaultCryptoRepository @Inject constructor() : CryptoRepository {
    override suspend fun getRealtimePrice(symbol: String): Result<CryptoAsset> = withContext(Dispatchers.IO) {
        delay(600) // Simulasi I/O
        if (Random.nextDouble() < 0.1) {
            return@withContext Result.failure(Exception("Jaringan bermasalah (Network Failure)"))
        }
        val mockPrice = when (symbol) {
            "BTC" -> 64000.0 + Random.nextDouble(-100.0, 100.0)
            "ETH" -> 3400.0 + Random.nextDouble(-20.0, 20.0)
            else -> 10.0 + Random.nextDouble(-0.5, 0.5)
        }
        Result.success(
            CryptoAsset(
                symbol = symbol,
                priceUsd = mockPrice,
                lastUpdated = System.currentTimeMillis()
            )
        )
    }
}
```

### Langkah 4: Presentation Layer (MVI)
Buat file `hands-on/m02/src/main/java/com/enterprise/m02/presentation/CryptoViewModel.kt`:
```kotlin
package com.enterprise.m02.presentation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.enterprise.m02.domain.CryptoAsset
import com.enterprise.m02.domain.GetCryptoPriceUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CryptoUiState(
    val isLoading: Boolean = false,
    val asset: CryptoAsset? = null,
    val errorMessage: String? = null
)

sealed interface CryptoIntent {
    data class FetchPrice(val symbol: String) : CryptoIntent
}

@HiltViewModel
class CryptoViewModel @Inject constructor(
    private val getCryptoPriceUseCase: GetCryptoPriceUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(CryptoUiState())
    val uiState: StateFlow<CryptoUiState> = _uiState.asStateFlow()

    fun handleIntent(intent: CryptoIntent) {
        when (intent) {
            is CryptoIntent.FetchPrice -> loadPrice(intent.symbol)
        }
    }

    private fun loadPrice(symbol: String) {
        _uiState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            getCryptoPriceUseCase(symbol)
                .onSuccess { data ->
                    _uiState.update { it.copy(isLoading = false, asset = data) }
                }
                .onFailure { err ->
                    _uiState.update { it.copy(isLoading = false, errorMessage = err.message) }
                }
        }
    }
}
```

Buat file `hands-on/m02/src/main/java/com/enterprise/m02/presentation/CryptoScreen.kt`:
```kotlin
package com.enterprise.m02.presentation

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun CryptoScreen(viewModel: CryptoViewModel) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        if (state.isLoading) {
            CircularProgressIndicator()
        } else {
            state.asset?.let {
                Text(text = "Asset: ${it.symbol}", style = MaterialTheme.typography.titleLarge)
                Text(text = "Price: $${String.format("%.2f", it.priceUsd)}", style = MaterialTheme.typography.headlineMedium)
            }
            state.errorMessage?.let {
                Text(text = "Error: $it", color = MaterialTheme.colorScheme.error)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { viewModel.handleIntent(CryptoIntent.FetchPrice("BTC")) }) {
                Text("Fetch BTC")
            }
            Button(onClick = { viewModel.handleIntent(CryptoIntent.FetchPrice("ETH")) }) {
                Text("Fetch ETH")
            }
        }
    }
}
```

---

## 13. Exercise

### Level Easy
Modifikasi `CryptoUiState` pada section *Hands-on Practice* untuk mendukung status timestamp format manusia (`HH:mm:ss`).
- **Kriteria Keberhasilan**: UI menampilkan teks `Terakhir diperbarui: 14:02:45` ketika data sukses diambil tanpa memicu recomposition berulang setiap detik.

### Level Medium
Tambahkan mekanisme cache fallback pada `DefaultCryptoRepository`. Jika jaringan menghasilkan `Result.failure`, repository harus mengembalikan data terakhir yang berhasil disimpan di variabel lokal (in-memory caching) disertai flag warning bahwa data tersebut adalah *stale data*.
- **Kriteria Keberhasilan**: 
  - Tidak terjadi crash saat status network failed.
  - State UI menampilkan banner "Menampilkan data lokal".
  - Thread-safety terjamin menggunakan `Mutex`.

### Level Hard
Buat custom Coroutine Dispatcher pool terisolasi (maksimal 2 thread) khusus untuk operasi Use Case enkripsi token, lalu inject dispatcher tersebut via Hilt Qualifier `@CryptoDispatcher`.
- **Kriteria Keberhasilan**:
  - Dibuat menggunakan `Executors.newFixedThreadPool(2).asCoroutineDispatcher()`.
  - Terdaftar di Hilt Module terpisah.
  - Dipastikan thread pool di-shutdown secara otomatis saat aplikasi dimatikan (*graceful termination*).

---

## 14. Challenge

### Studi Kasus: High-Frequency Stock Market Ticker Terminal
Rancang dan bangun sistem rendering market depth (*Order Book*) bursa saham skala enterprise dengan karakteristik:
1. **Spesifikasi Data Stream**: Menerima update harga via WebSocket mock sebanyak 50 data packet per detik (20ms interval).
2. **Kendala Keras (Hard Constraints)**:
   - UI Jetpack Compose tidak boleh mengalami frame drop di bawah 60 FPS pada perangkat mid-range.
   - Slot Table tidak boleh melakukan alokasi ulang untuk baris order yang tidak berubah nilai harganya (*stable identity diffing*).
   - Penggunaan memori tidak boleh bertambah secara konstan (*zero memory-leak footprint* selama 1 jam running).
3. **Instruksi Pengiriman Solusi**:
   - Dokumentasikan rancangan data-flow pipeline (diagram ASCII).
   - Tulis kode Reducer yang menerapkan *windowing aggregation* (mengumpulkan dan menggabungkan update dalam interval 100ms sebelum memancarkan state baru ke UI).
   - Sertakan unit test konkurensi Coroutine menggunakan `runTest` dan `StandardTestDispatcher` yang memverifikasi bahwa emisi 1.000 events dalam 1 detik hanya menghasilkan maksimum 10 UI emissions.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic
1. Apa fungsi utama dari Slot Table dalam runtime Jetpack Compose?
   - A. Menyimpan file cache bitmap gambar dari jaringan.
   - B. Struktur data linear penampung status pohon komposisi untuk in-place mutation recomposition.
   - C. Pengganti SQL database lokal untuk menyimpan state aplikasi.
   - D. Thread pool executor bawaan framework Android.
   *Jawaban*: **B**. Slot table adalah gap buffer yang menampung rekaman pohon composable secara mendatar untuk mengeksekusi recomposition secara efisien.

2. Mengapa anotasi `@Immutable` atau `@Stable` disarankan pada model UI State Compose?
   - A. Agar data class otomatis terenkripsi di memori.
   - B. Membantu compiler Compose menyimpulkan bahwa data tidak berubah di luar siklus Compose, mengizinkan *smart skipping* recomposition.
   - C. Mengizinkan class tersebut berjalan di thread terpisah secara otomatis.
   - D. Mengubah objek Java menjadi pointer C++ native.
   *Jawaban*: **B**. Mengizinkan compiler melewati composable jika argumen referensi tidak berubah (*recomposition skipping*).

3. Operator Kotlin Flow apa yang membuang data lama ketika consumer tertinggal dari producer yang cepat?
   - A. `filterNotNull()`
   - B. `conflate()`
   - C. `distinctUntilChanged()`
   - D. `buffer()`
   *Jawaban*: **B**. `conflate()` mengabaikan nilai antara (*skips intermediate values*) jika collector sedang sibuk memproses data sebelumnya.

4. Kapan lifecycle scope dari `@ViewModelScoped` dependency di Dagger/Hilt dihancurkan?
   - A. Setiap kali layar berotasi (Configuration change).
   - B. Ketika ViewModel induk dibersihkan via callback `onCleared()`.
   - C. Saat aplikasi masuk ke status background.
   - D. Setiap kali Intent baru diproses.
   *Jawaban*: **B**. `@ViewModelScoped` terikat penuh dengan siklus hidup instance ViewModel terkait.

5. Manakah metode pengumpulan (*collecting*) Flow yang direkomendasikan pada Jetpack Compose modern?
   - A. `flow.collect()` di dalam method Composable.
   - B. `flow.collectAsState()`
   - C. `flow.collectAsStateWithLifecycle()`
   - D. `GlobalScope.launch { flow.collect() }`
   *Jawaban*: **C**. Karena menghentikan langganan Flow ketika Activity/Fragment berada di bawah lifecycle minimum (`Lifecycle.State.STARTED`).

---

### Bagian 2: Intermediate
6. Bagaimana cara compiler Kotlin menangani fungsi `suspend` di bawah level bytecode?
   - A. Membuat kernel thread OS baru untuk tiap eksekusi method.
   - B. Mentransformasikan fungsi menjadi Finite State Machine berbasis Continuation Passing Style (CPS).
   - C. Mengonversi kode menjadi interrupt handler C++ native secara statik.
   - D. Menjalankan fungsi tersebut di background Service Android tersembunyi.
   *Jawaban*: **B**. Kompilator membongkar fungsi suspend menjadi state machine berbasis `Continuation` yang memetakan suspension point ke label integer.

7. Mengapa penggunaan `SharedFlow` dengan buffer tidak terbatas (`extraBufferCapacity = Int.MAX_VALUE`) dilarang pada aplikasi enterprise?
   - A. Menyebabkan aplikasi mengalami compile-time error.
   - B. Berpotensi memicu fatal crash Out-Of-Memory (OOM) saat terjadi backpressure dari producer tak terkontrol.
   - C. Menolak emisi data pertama (cold stream).
   - D. Menghambat thread UI utama secara synchronous.
   *Jawaban*: **B**. Buffer tak terbatas mengalokasikan heap tanpa batas jika collector terblokir, memicu crash alokasi memori.

8. Apa perbedaan mendasar antara Hilt `@InstallIn(SingletonComponent::class)` dan `@InstallIn(ActivityRetainedComponent::class)`?
   - A. Tidak ada perbedaan fungsional.
   - B. `SingletonComponent` hidup sepanjang proses aplikasi berjalan, sedangkan `ActivityRetainedComponent` bertahan melintasi configuration changes namun mati saat Activity dihancurkan permanen.
   - C. `ActivityRetainedComponent` tidak mendukung Coroutine Dispatcher.
   - D. `SingletonComponent` hanya bisa di-inject ke dalam Android Services.
   *Jawaban*: **B**. `ActivityRetainedComponent` mempertahankan dependensi saat rotasi layar, namun membebaskan memori saat Activity finish.

9. Apa yang terjadi jika blok `catch (e: Exception)` menelan `CancellationException` tanpa melemparnya kembali?
   - A. Performa aplikasi meningkat 20%.
   - B. Mekanisme cooperative cancellation terputus, coroutine terus berjalan di latar belakang meski scope telah dibatalkan.
   - C. StateFlow otomatis memancarkan status `null`.
   - D. Kompilator menolak mem-build APK.
   *Jawaban*: **B**. `CancellationException` adalah sinyal struktural Coroutine untuk pembatalan. Jika ditelan, coroutine tidak akan berhenti.

10. Mengapa interface `java.util.List` dianggap unstable oleh Compose Compiler metrics secara default?
    - A. Karena List adalah interface bawaan Java yang tidak menjamin sifat immutability pada runtime (bisa di-cast ke `MutableList`).
    - B. Karena ukuran List tidak bisa diketahui sebelum proses runtime.
    - C. Karena List menggunakan alokasi native memory.
    - D. Karena List tidak mengimplementasikan Serializable.
    *Jawaban*: **A**. Compiler Compose tidak dapat menjamin implementasi konkret List tidak dimutasi di luar pengawasannya, sehingga menandainya sebagai unstable parameter.

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario**: Aplikasi e-commerce mendadak mengalami lonjakan ANR (Application Not Responding) sebesar 8% di layar Checkout setelah rilis versi baru. Profiler menemukan thread UI (`main`) terblokir selama 6 detik. Ditemukan cuplikan kode:
    ```kotlin
    fun processCheckout() {
        viewModelScope.launch(Dispatchers.Main) {
            val cartData = localDatabase.getCartItemsDirect() // Synchronous Room Call
            val hash = calculateSha256Checksum(cartData)      // Heavy crypto
            _state.value = Success(hash)
        }
    }
    ```
    Bagaimana solusi rekayasa terbaik untuk mengatasi masalah ini secara permanen?
    - **Solusi**: Ubah DAO method Room menjadi fungsi `suspend` asinkron, dan pindahkan eksekusi operasi komputasi checksum SHA-256 ke `Dispatchers.Default`:
      ```kotlin
      fun processCheckout() {
          viewModelScope.launch {
              val cartData = withContext(Dispatchers.IO) { localDatabase.getCartItems() }
              val hash = withContext(Dispatchers.Default) { calculateSha256Checksum(cartData) }
              _state.update { State.Success(hash) }
          }
      }
      ```

12. **Skenario**: Pada aplikasi trading, pengguna melaporkan dialog peringatan "Koneksi Terputus" muncul berulang kali secara acak saat mereka berpindah dari mode portrait ke landscape, padahal koneksi internet sangat stabil. Kode UI:
    ```kotlin
    viewModel.networkErrorChannel.receiveAsFlow().collect { showDialog() }
    ```
    Mengapa ini terjadi pada saat rotasi layar, dan bagaimana standard enterprise memperbaikinya?
    - **Penyebab**: ViewModel menggunakan single-event strategy yang salah atau meng-emit ulang error saat recomposition / lifecycle re-attachment, atau Channel dibaca ulang tanpa kontrol siklus hidup UI (`LaunchedEffect` dipicu ulang setiap kali Activity di-recreate).
    - **Solusi**: Bungkus event ke dalam immutable StateFlow atau konsumsi side-effect di dalam `LaunchedEffect(Unit)` yang terikat pada event emission id unik, dan gunakan `repeatOnLifecycle(Lifecycle.State.STARTED)` guna mengisolasi konsumsi event dari recreate siklus hidup view.

13. **Skenario**: Tim QA melaporkan kebocoran memori (Memory Leak) 120MB yang terdeteksi via LeakCanary setelah masuk dan keluar dari modul Dynamic Feature `:feature:kyc` sebanyak 10 kali. Root object mengarah ke instance `KycImageProcessor` yang memegang referensi ke `Activity`.
    Bagaimana mendiagnosis dan memodifikasi desain dependensi Dagger/Hilt?
    - **Penyebab**: `KycImageProcessor` dianotasi dengan `@Singleton` di dalam graph `:core:di`, sementara ia menerima dependency `Context` berupa `ActivityContext`, bukan `ApplicationContext`. Akibatnya, instance Activity ditahan di root memory space aplikasi selama proses OS masih hidup.
    - **Solusi**: 
      1. Ubah injection context menjadi `@ApplicationContext context: Context`.
      2. Pindahkan scope `KycImageProcessor` menjadi scoped ke feature lifecycle (`@ActivityScope` atau `@ViewModelScoped` di dalam modul terkait), bukan `@Singleton`.
      3. Jalankan release explicit pada bitmap resource native via `bitmap.recycle()` pada callback teardown.

---

## 16. Summary

1. **Arsitektur Enterprise Modern**: Menggabungkan Clean Architecture dan MVI dengan *Unidirectional Data Flow* (UDF). Intent mentransmisikan aksi pengguna, Domain Use Case mengisolasi aturan bisnis independen dari framework, dan ViewModel merekayasa pembaruan status menjadi immutable state tunggal.
2. **Kinerja Runtime Compose**: Performa rendering optimal (60-120 FPS) menuntut pemahaman terhadap *Slot Table* dan *Snapshot State Engine*. Menandai model dengan `@Immutable` / `@Stable` serta menyediakan stable keys pada list dinamis mencegah overhead recomposition yang merusak fluiditas UI.
3. **Konkurensi & Lifecycle Alignment**: Hindari pengumpulan stream data reaktif via lifecycle scope yang salah. Kombinasi operator Kotlin Flow modern (`conflate`, `debounce`), isolasi Dispatchers (`IO`, `Default`, `Main`), dan konsumsi berbasis `collectAsStateWithLifecycle()` menjamin aplikasi bebas kebocoran memori, hemat daya, dan kebal dari ANR.