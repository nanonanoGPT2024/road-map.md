# BAB 03: Arsitektur Android Modern
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal/Lead Android Engineer diharapkan mampu:
*   **Merancang & Mengimplementasikan Arsitektur MVI (Model-View-Intent)** berbasis *Unidirectional Data Flow* (UDF) dengan jaminan *thread-safety*, deterministik, dan bebas *race condition*.
*   **Membangun Multi-Module Architecture Enterprise** (layer & feature-based) dengan meminimalisasi *build time* melalui Gradle build caching, API/implementation separation, serta isolasi dependensi.
*   **Mendesain Offline-First Sync Engine** dengan Single Source of Truth (SSOT) memanfaatkan Room, Coroutines Flow, dan WorkManager dengan strategi resolusi konflik deterministik.
*   **Mengoptimalkan Lifecycle-Aware UI Pipeline** pada Jetpack Compose dengan `collectAsStateWithLifecycle` untuk mencegah *resource leakage* dan *unnecessary recomposition*.
*   **Menerapkan Production-Grade Error Handling** menggunakan Result Monad Pattern dan domain business invariant validation.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
*   **Kotlin Advanced**: Generics (variance: `in`, `out`), Coroutines (Job, SupervisorJob, CoroutineScope, Context, Exception Handling), Coroutine Concurrency (`Mutex`, `AtomicReference`).
*   **Reactive Programming**: Perbedaan mendalam `StateFlow`, `SharedFlow`, dan `Channel` (Buffer overflow strategies, replay, hot vs cold stream).
*   **Modern Android Stack**: Jetpack Compose state-snapshot system, Room persistence library, Android lifecycle architecture components.
*   **Build Systems**: Gradle Kotlin DSL (`build.gradle.kts`), Version Catalogs (`libs.versions.toml`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Unidirectional Data Flow (UDF) & MVI State Machine

Pada arsitektur enterprise berskala besar, MVVM klasik sering mengalami degradasi menjadi *anti-pattern* "God ViewModel" dengan multiple mutable state variables yang dimutasi dari berbagai *asynchronous coroutines*, memicu *race condition* dan *inconsistent state*.

MVI mengatasi ini dengan memodelkan interaksi pengguna sebagai mesin status hingga (*Finite State Machine* / FSM):

```
       [User Interaction / UI Events]
                     │
                     ▼ (Intent)
            ┌─────────────────┐
            │  Intent Channel │
            └────────┬────────┘
                     ▼
           [ViewModel Reducer] <─── [Domain / UseCases]
                     │
         (Atomic State Transition)
                     │
                     ▼ (New Immutable State)
            ┌─────────────────┐
            │    StateFlow    │
            └────────┬────────┘
                     ▼ (Render)
            [Compose UI Tree]
```

*   **Intent**: Objek *immutable* yang merepresentasikan niat pengguna atau aksi sistem (misal: `AddToCart`, `RetryPayment`).
*   **State**: *Single Source of Truth* dari UI pada satu waktu. Bersifat absolut dan *immutable*. Komponen UI tidak boleh memiliki *state logic* terpisah di luar visual rendering.
*   **Reducer**: Fungsi murni (*pure function*) atau eksekusi terkontrol yang menerima `(PreviousState, MutationResult) -> NewState`. Tidak boleh ada *side-effects* di dalam fungsi reduksi.
*   **Side Effect**: Kejadian satu kali (*one-off events*) seperti navigasi, Toast, atau analitik, diekspos secara eksklusif via `Channel` yang dikonsumsi sebagai event, bukan state.

#### 3.2 Internal Compose Recomposition Loop & State Snapshot

Jetpack Compose menggunakan **Snapshot State System**. Setiap kali membaca properti `State<T>`, Compose mendaftarkan pembacaan tersebut pada *current recomposition scope*. 

```
[Snapshot.sendApplyNotifications()]
               │
               ▼
[GlobalSnapshotManager]
               │
               ▼ (State mutated)
[Recomposer: Detect Invalidated Nodes]
               │
               ▼
[LayoutNode.measure() -> LayoutNode.draw()]
```

Jika ViewModel memancarkan *state* baru di mana referensi instans berubah tetapi nilainya ekuivalen (gagal mengimplementasikan kestabilan objek/@Immutable), *Recomposer* akan memicu recomposition pohon UI secara berlebihan (*over-recomposition*). Oleh karena itu, *state* harus didesain stabil dengan `@Immutable` atau `@Stable` contract.

#### 3.3 Multi-Module Architecture Graph

Pada aplikasi enterprise dengan puluhan insinyur, struktur *monolithic module* (`:app`) menyebabkan *merge conflicts* tinggi dan *compilation time* linear terhadap ukuran kode. Desain modularisasi standar industri membagi aplikasi secara modular berorientasi fitur (*graph isolation*):

```
                       ┌─────────┐
                       │  :app   │
                       └───┬─┬───┘
            ┌──────────────┘ │ └──────────────┐
            ▼                ▼                ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │:feature:cart│  │:feature:auth│  │:feature:home│
     └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
            │                │                │
            └───────────┬────┴────┬───────────┘
                        ▼         ▼
                 ┌──────────┐ ┌──────────┐
                 │:core:ui  │ │:core:dom │
                 └─────┬────┘ └───┬───┬──┘
                       │          │   │
            ┌──────────┴──────────┘   │
            ▼                         ▼
     ┌─────────────┐           ┌─────────────┐
     │:core:common │           │:core:data   │
     └─────────────┘           └───┬─────┬───┘
                                   │     │
                        ┌──────────┘     └──────────┐
                        ▼                           ▼
                 ┌─────────────┐             ┌─────────────┐
                 │:core:network│             │:core:db     │
                 └─────────────┘             └─────────────┘
```

Prinsip dependensi:
*   Feature modules **tidak boleh saling bergantung** secara langsung. Komunikasi antar-fitur diarahkan melalui deep links atau Core Navigation Abstractions di `:core:navigation`.
*   Feature modules hanya bergantung pada `:core:domain`, `:core:ui`, dan `:core:common`.
*   `:core:domain` tidak boleh memiliki dependensi Android Framework (pure Kotlin library).

---

### 4. Why & What

| Dimensi | Legacy Pattern (MVVM Tradisional) | Enterprise Modern (Clean MVI + Modular) |
| :--- | :--- | :--- |
| **State Management** | Multiple `MutableLiveData` atau `MutableStateFlow` tersebar. | Single immutable `UiState` sealed interface via UDF. |
| **Concurrency Control** | Mutasi variabel paralel memicu *race condition*. | Serialisasi via Actor/Channel atau Reducer dengan Atomic Updates (`update { ... }`). |
| **Scalability** | Lambat dikompilasi, *coupling* tinggi antar kelas. | Skalabilitas tinggi via Multi-module (paralelisasi build, dynamic feature). |
| **Testability** | Pengujian UI dan ViewModel memerlukan mock kompleks. | Reducer murni dapat diuji secara deterministik tanpa mock coroutine kompleks. |
| **Offline Handling** | Penanganan parsial di Repository, cache manual. | SSOT terisolasi: Database sebagai satu-satunya representasi data UI (*Room as SSOT*). |

---

### 5. How (Workflow Detail)

Alur eksekusi request modern end-to-end:

1.  **UI Event Emission**: Komponen Compose memicu lambda callback `onIntent(CartIntent.CheckoutClicked)`.
2.  **Intent Ingestion**: ViewModel menerima intent melalui coroutine pipeline non-blocking (`Channel` bertipe buffer).
3.  **Domain Processing**: ViewModel mengeksekusi `CheckoutUseCase`, yang memvalidasi *business rules* murni (misal: validasi minimum nominal transaksi).
4.  **Data Layer Coordination**: Repository mengorkestrasi *data synchronization*:
    *   Tulis data sementara ke Room Database dengan flag `SyncStatus.PENDING`.
    *   Database Flow secara otomatis memancarkan status terbaru ke ViewModel.
    *   Picukan `WorkManager` untuk sinkronisasi latar belakang jika koneksi internet terputus, atau kirim langsung via Network Client dengan idempotency key.
5.  **State Reduction**: ViewModel menerima `Result<T>` dari UseCase, kemudian memanggil `_uiState.update { current -> reducer(current, mutation) }`.
6.  **UI Recomposition**: Compose Tree yang memantau UI State via `collectAsStateWithLifecycle()` merekomposisi komponen yang terinvalidasi secara efisien.

---

### 6. Analogy & Diagram ASCII

#### Analogi Mesin Transaksi Finansial (Ledger ATM)
Bayangkan mesin ATM: Anda tidak dapat langsung mengambil uang dari brankas (Database) atau mengubah saldo di layar (UI State) secara manual. 
1. Anda menekan tombol "Tarik Saldo" (**Intent**).
2. Sistem mencatat permintaan Anda ke jurnal transaksi (**Event Queue**).
3. Komputer sentral memverifikasi saldo dan limit (**Domain UseCase**).
4. Komputer sentral menginstruksikan modul pengeluaran kas dan mencetak struk (**Reducer** memutasi state).
5. Layar berubah menunjukkan sisa saldo terkini (**Immutable Rendered State**).

#### Diagram Transisi State Deterministik (MVI Reducer)

```
               [State: Idle]
                     │
                     │ Intent: LoadCart
                     ▼
           [State: Loading(showSkeleton = true)]
                     │
       ┌─────────────┴─────────────┐
       │ (Success)                 │ (Failure)
       ▼                           ▼
[State: Success(items)]     [State: Error(message, canRetry = true)]
       │
       │ Intent: UpdateQuantity(id, qty)
       ▼
[State: Success(items, isMutating = true)] (Optimistic Update)
       │
       ├─── Network Success ───> [State: Success(items, isMutating = false)]
       │
       └─── Network Failure ───> [State: Success(rollbackItems, errorToast)]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Counter MVI Menggunakan Atomic StateFlow

```kotlin
// UI State
data class CounterState(val count: Int = 0, val isLoading: Boolean = false)

// Intent
sealed interface CounterIntent {
    data object Increment : CounterIntent
    data object Decrement : CounterIntent
}

// ViewModel Reducer
class CounterViewModel : ViewModel() {
    private val _state = MutableStateFlow(CounterState())
    val state: StateFlow<CounterState> = _state.asStateFlow()

    fun handleIntent(intent: CounterIntent) {
        when (intent) {
            is CounterIntent.Increment -> _state.update { it.copy(count = it.count + 1) }
            is CounterIntent.Decrement -> _state.update { it.copy(count = it.count - 1) }
        }
    }
}
```

#### 7.2 Practical Example: Enterprise E-Commerce Cart Engine (Production-Grade)

##### 1. Domain Layer (`:core:domain`)
```kotlin
package com.enterprise.core.domain.model

sealed interface AppResult<out T> {
    data class Success<T>(val data: T) : AppResult<T>
    data class Error(val cause: DomainException) : AppResult<Nothing>
}

sealed class DomainException(message: String) : Exception(message) {
    data object NetworkTimeout : DomainException("Koneksi internet bermasalah.")
    data object OutOfStock : DomainException("Stok produk tidak mencukupi.")
    data class Unhandled(val throwable: Throwable) : DomainException(throwable.localizedMessage ?: "Unknown error")
}

data class CartItem(
    val id: String,
    val productId: String,
    val name: String,
    val price: Double,
    val quantity: Int
)

// Invariant Business Rule Validation
data class Cart(
    val items: List<CartItem> = emptyList()
) {
    val totalPrice: Double get() = items.sumOf { it.price * it.quantity }
    val totalQuantity: Int get() = items.sumOf { it.quantity }

    init {
        require(items.none { it.quantity < 0 }) { "Kuantitas tidak boleh negatif." }
    }
}
```

##### 2. Use Case Interactor (`:core:domain`)
```kotlin
package com.enterprise.core.domain.usecase

import com.enterprise.core.domain.model.*
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

interface CartRepository {
    fun getCartStream(): Flow<Cart>
    suspend fun updateItemQuantity(productId: String, delta: Int): AppResult<Unit>
    suspend fun syncCart(): AppResult<Unit>
}

class UpdateCartQuantityUseCase @Inject constructor(
    private val cartRepository: CartRepository
) {
    suspend operator fun invoke(productId: String, delta: Int): AppResult<Unit> {
        if (delta == 0) return AppResult.Success(Unit)
        return cartRepository.updateItemQuantity(productId, delta)
    }
}
```

##### 3. Data Layer Implementation with Room SSOT (`:core:data`)
```kotlin
package com.enterprise.core.data.repository

import androidx.room.*
import com.enterprise.core.domain.model.*
import com.enterprise.core.domain.usecase.CartRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Entity(tableName = "cart_items")
data class CartItemEntity(
    @PrimaryKey val productId: String,
    val cartId: String,
    val name: String,
    val price: Double,
    val quantity: Int,
    val syncPending: Boolean = false
)

@Dao
interface CartDao {
    @Query("SELECT * FROM cart_items")
    fun observeAll(): Flow<List<CartItemEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(items: List<CartItemEntity>)

    @Query("UPDATE cart_items SET quantity = quantity + :delta, syncPending = 1 WHERE productId = :productId")
    suspend fun updateQuantity(productId: String, delta: Int)
}

@Singleton
class CartRepositoryImpl @Inject constructor(
    private val cartDao: CartDao,
    private val remoteApi: CartNetworkDataSource
) : CartRepository {

    override fun getCartStream(): Flow<Cart> {
        return cartDao.observeAll().map { entities ->
            Cart(
                items = entities.map {
                    CartItem(
                        id = it.cartId,
                        productId = it.productId,
                        name = it.name,
                        price = it.price,
                        quantity = it.quantity
                    )
                }
            )
        }
    }

    override suspend fun updateItemQuantity(productId: String, delta: Int): AppResult<Unit> {
        return try {
            // Optimistic update locally
            cartDao.updateQuantity(productId, delta)
            // Trigger remote network call
            val response = remoteApi.patchQuantity(productId, delta)
            if (response.isSuccessful) {
                AppResult.Success(Unit)
            } else {
                AppResult.Error(DomainException.OutOfStock)
            }
        } catch (e: Exception) {
            AppResult.Error(DomainException.Unhandled(e))
        }
    }

    override suspend fun syncCart(): AppResult<Unit> {
        // Implementation for WorkManager or background sync
        return AppResult.Success(Unit)
    }
}

interface CartNetworkDataSource {
    suspend fun patchQuantity(productId: String, delta: Int): NetworkResponse
}
data class NetworkResponse(val isSuccessful: Boolean)
```

##### 4. Presentation State & Reducer Pipeline (`:feature:cart`)
```kotlin
package com.enterprise.feature.cart

import androidx.compose.runtime.Immutable
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.enterprise.core.domain.model.Cart
import com.enterprise.core.domain.model.AppResult
import com.enterprise.core.domain.usecase.CartRepository
import com.enterprise.core.domain.usecase.UpdateCartQuantityUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@Immutable
data class CartUiState(
    val cart: Cart = Cart(),
    val isSyncing: Boolean = false,
    val errorMessage: String? = null
)

sealed interface CartIntent {
    data object Refresh : CartIntent
    data class AdjustQuantity(val productId: String, val delta: Int) : CartIntent
    data object DismissError : CartIntent
}

sealed interface CartSideEffect {
    data class ShowToast(val message: String) : CartSideEffect
    data class NavigateToCheckout(val orderId: String) : CartSideEffect
}

@HiltViewModel
class CartViewModel @Inject constructor(
    private val cartRepository: CartRepository,
    private val updateQuantityUseCase: UpdateCartQuantityUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(CartUiState())
    val uiState: StateFlow<CartUiState> = _uiState.asStateFlow()

    private val _effectChannel = Channel<CartSideEffect>(capacity = Channel.BUFFERED)
    val effect: Flow<CartSideEffect> = _effectChannel.receiveAsFlow()

    init {
        observeCartData()
    }

    private fun observeCartData() {
        cartRepository.getCartStream()
            .onEach { cart ->
                _uiState.update { currentState ->
                    currentState.copy(cart = cart, isSyncing = false)
                }
            }
            .catch { throwable ->
                _uiState.update { it.copy(errorMessage = throwable.localizedMessage) }
            }
            .launchIn(viewModelScope)
    }

    fun dispatch(intent: CartIntent) {
        when (intent) {
            is CartIntent.AdjustQuantity -> handleQuantityAdjustment(intent.productId, intent.delta)
            is CartIntent.Refresh -> syncCartData()
            is CartIntent.DismissError -> _uiState.update { it.copy(errorMessage = null) }
        }
    }

    private fun handleQuantityAdjustment(productId: String, delta: Int) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true) }
            when (val result = updateQuantityUseCase(productId, delta)) {
                is AppResult.Success -> {
                    // State di-update otomatis melalui Room getCartStream Flow
                }
                is AppResult.Error -> {
                    _uiState.update { it.copy(isSyncing = false) }
                    _effectChannel.send(CartSideEffect.ShowToast(result.cause.message ?: "Failed"))
                }
            }
        }
    }

    private fun syncCartData() {
        viewModelScope.launch {
            _uiState.update { it.copy(isSyncing = true) }
            cartRepository.syncCart()
        }
    }
}
```

##### 5. Declarative UI Component (`:feature:cart`)
```kotlin
package com.enterprise.feature.cart.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.enterprise.feature.cart.*

@Composable
fun CartScreen(
    viewModel: CartViewModel,
    onNavigateCheckout: (String) -> Unit,
    snackbarHostState: SnackbarHostState
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(viewModel.effect) {
        viewModel.effect.collect { effect ->
            when (effect) {
                is CartSideEffect.ShowToast -> {
                    snackbarHostState.showSnackbar(effect.message)
                }
                is CartSideEffect.NavigateToCheckout -> {
                    onNavigateCheckout(effect.orderId)
                }
            }
        }
    }

    CartContent(
        uiState = uiState,
        onIntent = viewModel::dispatch
    )
}

@Composable
internal fun CartContent(
    uiState: CartUiState,
    onIntent: (CartIntent) -> Unit,
    modifier: Modifier = Modifier
) {
    Box(modifier = modifier.fillMaxSize()) {
        if (uiState.cart.items.isEmpty() && !uiState.isSyncing) {
            Text(text = "Keranjang kosong", modifier = Modifier.align(Alignment.Center))
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(
                    items = uiState.cart.items,
                    key = { item -> item.productId }
                ) { item ->
                    CartItemRow(
                        name = item.name,
                        quantity = item.quantity,
                        price = item.price,
                        onIncrease = { onIntent(CartIntent.AdjustQuantity(item.productId, 1)) },
                        onDecrease = { onIntent(CartIntent.AdjustQuantity(item.productId, -1)) }
                    )
                }
            }
        }

        if (uiState.isSyncing) {
            CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
        }
    }
}

@Composable
private fun CartItemRow(
    name: String,
    quantity: Int,
    price: Double,
    onIncrease: () -> Unit,
    onDecrease: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(text = name, style = MaterialTheme.typography.titleMedium)
                Text(text = "Rp $price", style = MaterialTheme.typography.bodySmall)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onDecrease) { Text("-") }
                Text(text = "$quantity", modifier = Modifier.padding(horizontal = 8.dp))
                IconButton(onClick = onIncrease) { Text("+") }
            }
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Dynamic Driver Ledger & Order Dispatching pada Jaringan Seluler 3G/Edge
*   **Konteks**: Aplikasi driver ride-hailing memproses puluhan event order & transaksi ledger per detik dalam kondisi latensi tinggi, disconnect mendadak (*tunnel effect*), dan restart proses akibat Android Low Memory Killer (LMK).
*   **Kegagalan Sistem Sebelumnya**: 
    1. Penggunaan `SharedFlow` standar untuk booking orders menyebabkan hilangnya order baru jika UI recomposition sedang terhenti.
    2. Data balance pengemudi tidak sinkron (*divergent state*) antara cache in-memory dan database lokal jika koneksi putus di tengah jalan.
*   **Solusi Rekayasa**:
    1. **Room WAL (Write-Ahead Logging) as Canonical SSOT**: Seluruh event network langsung di-insert ke Room dengan sequence mutation token. ViewModel tidak memegang data list in-memory selain StateFlow yang bersumber langsung dari Room DAO Flow.
    2. **Idempotency Execution Engine**: Setiap request intent ke remote API menyertakan UUID yang dibuat saat intent diinisiasi di client. Jika koneksi gagal, `WorkManager` melakukan retry dengan backoff eksponensial menggunakan idempotency key yang sama, mencegah *double execution/ledger charging*.
    3. **Buffer Management**: Penggunaan `Channel(Channel.BUFFERED)` untuk intent dan side-effects guna menjamin event tidak pernah tereduksi saat aplikasi berada pada lifecycle `STOPPED`.

---

### 9. Trade-offs

| Pendekatan Arsitektural | Keuntungan (Pros) | Biaya & Kompensasi (Cons/Trade-offs) |
| :--- | :--- | :--- |
| **Strict MVI via UDF** | *Traceability* absolut; state deterministik dan mudah di-*reproduce* saat debugging; *zero race condition*. | *Boilerplate* tinggi: perlu mendefinisikan Intent, State, Reducer, dan Effect untuk fitur sederhana. |
| **Multi-Module Graph Isolations** | *Parallel compilation*; pemisahan kepemilikan kode per squad teknis; mencegah *spaghetti code*. | Konfigurasi Gradle kompleks; overhead pemeliharaan dependency injection (Hilt component sharing) dan navigasi. |
| **Room SSOT + Network Sync** | Aplikasi berfungsi 100% offline; data rendering instan; konsistensi state UI terjamin. | Storage I/O overhead; harus menangani *conflict resolution policy* (Client-Wins vs Server-Wins). |
| **Compose State Hoisting** | Visual state decoupling; preview tooling berfungsi optimal; testability komponen UI murni. | Terjadinya *prop-drilling* jika arsitektur tree terlalu dalam (harus diimbangi CompositionLocal secara bijak). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Variabel Langsung pada Collection di Data Class
*   **Problem**: Menggunakan `state.copy(items = state.items.apply { add(newItem) })`.
*   **Akibat**: Referensi memori instans `List` tidak berubah. Jetpack Compose Snapshot Engine menganggap tidak ada modifikasi, sehingga **recomposition tidak dipicu**.
*   **Solusi**: Selalu buat list baru: `state.copy(items = state.items + newItem)`.

#### 2. Lifecycle Unaware Flow Collection pada Compose
*   **Problem**: Menggunakan `flow.collectAsState()` biasa di dalam Compose UI.
*   **Akibat**: Emisi Flow tetap berjalan saat aplikasi berada di latar belakang (*background*), menyebabkan kebocoran memori, boros baterai, dan crash jika memicu transisi UI saat app di-background.
*   **Solusi**: Gunakan dependensi `androidx.lifecycle:lifecycle-runtime-compose` dan panggil `flow.collectAsStateWithLifecycle()`.

#### 3. Blocking Dispatcher pada Reducer ViewModel
*   **Problem**: Menjalankan enkripsi data, parsing JSON, atau DB read langsung di block utama `viewModelScope` tanpa `withContext(Dispatchers.IO)`.
*   **Akibat**: *Main thread freeze*, menyebabkan penurunan frame-rate (jank) atau Android App Not Responding (ANR).
*   **Solusi**: Alokasikan dispatcher secara eksplisit via dependency injection (`@IoDispatcher private val ioDispatcher: CoroutineDispatcher`).

---

### 11. Best Practices (Production Checklist)

- [ ] **State Immutability**: Semua deklarasi `UiState` menggunakan `data class` atau `sealed interface` dengan semua parameter dideklarasikan sebagai `val`.
- [ ] **Stable Collections**: Gunakan Kotlinx Immutable Collections (`ImmutableList<T>`, `PersistentList<T>`) pada UI state guna menjamin Compose Runtime Skip Recomposition.
- [ ] **Single Source of Truth**: UI tidak boleh mengupdate data lokal secara langsung; Repository menulis ke database, lalu database mengalirkan (*stream*) state ke UI via Flow.
- [ ] **Idempotent Network Calls**: Seluruh mutasi data menyertakan Client-Side Generated UUID (Idempotency Key).
- [ ] **Proguard/R8 Rules**: Setiap data class model jaringan/domain dilindungi dari *obfuscation* reflection jika menggunakan GSON/Moshi (`@Keep` atau explicit Proguard rules).
- [ ] **Explicit Module Boundaries**: Atur visibilitas internal Gradle. Jangan mengekspos dependency internal via `api`; gunakan `implementation`.

---

### 12. Hands-on Practice

Simpan seluruh hasil latihan pada folder: `hands-on/m02/`

#### Struktur Modul Latihan:
```
hands-on/m02/
├── domain/
│   ├── UserProfile.kt
│   └── UpdateProfileUseCase.kt
├── data/
│   ├── ProfileDao.kt
│   └── ProfileRepositoryImpl.kt
└── presentation/
    ├── ProfileUiState.kt
    ├── ProfileViewModel.kt
    └── ProfileScreen.kt
```

#### Langkah Instruksi:
1.  Buka terminal dan navigasi ke direktori workspace Anda.
2.  Implementasikan file `hands-on/m02/domain/UserProfile.kt` yang memuat domain model immutable dengan validasi invariant (misal: panjang nama minimal 3 karakter).
3.  Buat `UpdateProfileUseCase.kt` yang mengembalikan `Flow<AppResult<UserProfile>>`.
4.  Pada `ProfileViewModel.kt`, buat mesin state berbasis `MutableStateFlow<ProfileUiState>` dengan reduksi fungsi:
    ```kotlin
    fun onAction(action: ProfileAction)
    ```
5.  Uji skenario: Kirim *Action* secara masif (100 concurrent emissions menggunakan `coroutineScope`) dan pastikan nilai state akhir deterministik tanpa inkonsistensi.

---

### 13. Exercise

#### Level 1 - Easy
Ubah implementasi `MutableLiveData` tradisional pada modul sederhana menjadi `StateFlow` dan implementasikan sealed interface `UiState` yang mencakup 3 cabang status: `Loading`, `Success(val data: String)`, dan `Error(val message: String)`.

#### Level 2 - Medium
Implementasikan *Search Query Debounce Pipeline* di ViewModel. 
*   Tangani `Intent.Search(val query: String)`.
*   Terapkan operator Flow: `debounce(300)`, `distinctUntilChanged()`, dan `flatMapLatest` untuk memanggil Search UseCase.
*   Pastikan operasi pencarian sebelumnya dibatalkan (*cancelled*) jika query baru diketik sebelum timeout tercapai.

#### Level 3 - Hard
Rancang modul Offline-First Repository synchronization:
*   Kondisi: Data lokal di Room Entity memiliki properti `version: Long` dan `syncStatus: SyncStatus (SYNCED, PENDING_UPDATE)`.
*   Saat jaringan tersedia kembali, repository harus mengunggah seluruh item yang `PENDING_UPDATE`.
*   Jika server merespons HTTP 409 (Conflict), Repository wajib memicu algoritma resolusi Three-Way Merge: Field yang diubah secara lokal dipertahankan, sedangkan field yang tidak berubah di lokal diganti dengan data terbaru dari Server.

---

### 14. Challenge

**Skenario**: Sistem Real-Time Auction (Lelang Online Enterprise)

Rancang dan bangun arsitektur sistem bidding multi-screen untuk aplikasi enterprise:
1.  **High-Frequency Updates**: Harga barang lelang di-update melalui WebSocket dengan frekuensi hingga 50 kali per detik.
2.  **Jaminan UI Render**: Komponen Compose UI tidak boleh *jank* (harus mempertahankan 60/120 FPS). Recomposition wajib dibatasi maksimal hanya pada Text harga terkini, tanpa merender ulang kontainer layar lainnya.
3.  **Local Concurrency**: Pengguna dapat memencet tombol "Bid +$1" secepat mungkin. Sistem harus mengantrekan (*queue*) intent, menguji saldo lokal, menerapkan *optimistic update* pada UI, dan jika panggilan WebSocket gagal, sistem harus melakukan rollback state secara halus tanpa merusak sequence event bidding yang sedang berjalan.
4.  **Tantangan Ekstra**: Jangan gunakan library eksternal selain Kotlin Coroutines/Flow, AndroidX Room, dan Jetpack Compose. Tidak diperbolehkan menggunakan operator blocking atau synchronized lock Java. Seluruh konkurensi harus dikelola murni via Coroutines Flow primitives.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa Compose State dianjurkan berupa `Immutable` atau `Stable`?**
   * *Jawaban*: Agar *Compose Compiler* dapat menyimpulkan bahwa objek tersebut tidak akan berubah nilainya tanpa menciptakan referensi baru, sehingga Compose dapat melewatkan (*smart skip*) proses recomposition pada composable function jika parameternya tidak berubah.

2. **Apa perbedaan fungsional utama antara `StateFlow` dan `SharedFlow`?**
   * *Jawaban*: `StateFlow` adalah hot stream yang selalu menyimpan dan mempertahankan nilai status terakhir (*current value*) serta memerlukan initial value. Sedangkan `SharedFlow` adalah hot stream yang dapat memiliki konfigurasi replay buffer (bisa bernilai 0) dan biasanya digunakan untuk event broadcast tanpa harus selalu menyimpan nilai terakhir.

3. **Kapan kita harus menggunakan `Channel` dibandingkan `SharedFlow` untuk Side-Effects?**
   * *Jawaban*: Gunakan `Channel` jika event tersebut hanya boleh dikonsumsi tepat **satu kali** oleh satu observer (*single subscriber execution*, misal: transaksi payment atau navigasi). `SharedFlow` cocok untuk broadcast event yang bisa didengar oleh nol, satu, atau banyak observer sekaligus.

4. **Mengapa arsitektur Clean melarang modul `:core:domain` memiliki dependensi terhadap Android Framework SDK (`android.*`)?**
   * *Jawaban*: Untuk menjaga logika bisnis independen dari platform, meningkatkan portabilitas kode, mempercepat eksekusi unit test (menghilangkan kebutuhan Robolectric/Mockk Android), serta mencegah kebocoran lifecycle ke business logic.

5. **Apa fungsi dari `Snapshot.sendApplyNotifications()` secara internal pada Compose?**
   * *Jawaban*: Berfungsi untuk memvalidasi dan mempublikasikan modifikasi state ke seluruh observer runtime Compose, memicu Recomposer untuk mendeteksi node Compose mana saja yang perlu direkomposisi.

#### Bagian 2: Intermediate (5 Soal)
6. **Apa bahaya memanggil `SharedFlow.emit()` dari background thread tanpa buffer yang cukup jika strategy backpressure adalah `BufferOverflow.SUSPEND`?**
   * *Jawaban*: Emisi akan melakukan suspend (block coroutine) hingga collector membaca data tersebut. Jika collector terhenti (misal lifecycle screen berhenti), thread producer bisa tertahan (*deadlock risk* atau *hanging coroutines*).

7. **Jelaskan perbedaan operator Flow `flatMapLatest`, `flatMapMerge`, dan `flatMapConcat` dalam usecase pencarian teks!**
   * *Jawaban*: `flatMapLatest` akan membatalkan flow transformasi sebelumnya ketika data baru masuk (sangat ideal untuk input pencarian). `flatMapMerge` mengeksekusi semua transformasi secara paralel tanpa antrean. `flatMapConcat` menunggu transformasi data sebelumnya selesai secara sekuensial sebelum memproses data berikutnya.

8. **Mengapa fungsi update state pada ViewModel direkomendasikan menggunakan `_uiState.update { ... }` daripada `_uiState.value = ...`?**
   * *Jawaban*: `_uiState.update { ... }` beroperasi secara thread-safe menggunakan *atomic compare-and-set* (CAS loop). Hal ini mencegah hilangnya pembaruan status (*lost update*) ketika terjadi multiple mutation calls secara simultan dari thread berbeda.

9. **Bagaimana cara mencegah memory leak ketika mengamati Database Flow pada Jetpack Compose?**
   * *Jawaban*: Gunakan lifecycle-aware collector, yaitu `collectAsStateWithLifecycle(minActiveState = Lifecycle.State.STARTED)` pada UI composable function, yang akan otomatis menghentikan (*pause*) downstream subscription saat Activity/Fragment masuk ke background (`STOPPED`).

10. **Apa perbedaan antara Gradle module configuration `api` dan `implementation` pada build performance?**
    * *Jawaban*: `implementation` menyembunyikan dependensi internal dari consumer module. Jika dependensi tersebut berubah, Gradle hanya perlu mengompilasi ulang modul tersebut, bukan modul di atasnya (*compile avoidance*). `api` membocorkan dependensi secara transitif sehingga jika dependensi internal berubah, seluruh downstream module wajib dikompilasi ulang, yang memperlambat build time.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1**:
    Sebuah aplikasi FinTech mengalami anomali: Saat pengguna menekan tombol "Bayar", lalu segera merotasi layar smartphone, transaksi terkirim dua kali ke Payment Gateway. 
    * *Pertanyaan*: Apa akar masalah arsitektur ini dan bagaimana solusi deterministiknya?
    * *Jawaban*: ViewModel kemungkinan memicu network call di dalam UI event handler tanpa idempotency check, atau effect event di-collect ulang akibat re-subscription pada konfigurasi baru. Solusi: Gunakan ViewModel Scope dengan mutasi state via atomic check flag (`isProcessing`), pasang *Idempotency-Key* berbasis transaction UUID pada payload HTTP header, dan tangani request trigger via ViewModel scope yang selamat dari rekreasi konfigurasi layar.

12. **Skenario Kasus 2**:
    Aplikasi Anda memiliki module dependency graph berikut: `:feature:checkout` bergantung pada `:core:database`. Lead Engineer meminta arsitektur diubah agar `:feature:checkout` tidak lagi memiliki referensi langsung ke `:core:database`.
    * *Pertanyaan*: Mengapa permintaan Lead Engineer benar menurut Clean Architecture, dan bagaimana langkah refactoring-nya?
    * *Jawaban*: Akses langsung modul feature ke database melanggar prinsip *Dependency Inversion* dan memicu coupling tinggi antara UI/Domain dengan implementasi storage konkret. Solusi: Buat interface abstraction `CheckoutRepository` di `:core:domain`. Biarkan `:core:data` mengimplementasikan repository tersebut dan mengakses `:core:database`. Modul `:feature:checkout` selanjutnya hanya boleh bergantung pada `:core:domain` dan mengonsumsi interface via Dependency Injection (Dagger/Hilt).

13. **Skenario Kasus 3**:
    Pada production monitoring tercatat peningkatan drastis metrik ANR (*Application Not Responding*) sebesar 15% pada entry-level Android devices saat pengguna membuka halaman Katalog dengan 1.000 produk. Database Room sudah menggunakan pagination (Paging 3).
    * *Pertanyaan*: Di mana kemungkinan letak bottleneck arsitekturnya?
    * *Jawaban*: Bottleneck kemungkinan terletak pada: 
      1. Komposisi item list tidak menerapkan `key` stabil pada `items(items, key = { it.id })`, menyebabkan *lazy layout* mengalokasikan ulang seluruh view memory saat scroll.
      2. Domain mapping yang kompleks (seperti kalkulasi diskon atau format mata uang berulang) dijalankan langsung di Main Thread di dalam Composable Composable Scope alih-alih di-map di Background Thread (IO/Default Dispatcher) sebelum dipancarkan ke UI State.
      3. Properti list model menggunakan standard Kotlin `List` (unstable) sehingga Compose Runtime melakukan recomposition pada seluruh item row saat scroll terjadi.

---

### 16. Summary

*   **MVI & UDF** memberikan reliabilitas mutlak bagi aplikasi enterprise dengan memastikan State bersifat read-only dan Intent diolah melalui reducer yang deterministik.
*   **Modularisasi** bukan sekadar memecah folder, melainkan memotong siklus dependensi dengan mematuhi prinsip Clean Architecture: UI bergantung pada Domain, Implementasi Data diisolasi di Data Layer.
*   **Single Source of Truth (SSOT)** melalui Room menjamin integritas data offline-first, di mana Network DataSource bertindak sebagai *synchronizer*, bukan penentu utama tampilan visual.
*   **Jetpack Compose Lifecycle Integration** wajib ditegakkan via `collectAsStateWithLifecycle` untuk mencegah konsumsi daya yang tidak perlu dan *race condition* saat backgrounding.
*   **Production Robustness** ditentukan oleh penanganan kesalahan berbasis domain monad (`AppResult`), pembatasan recomposition via model immutability, dan mitigasi concurrency melalui *atomic primitives*.