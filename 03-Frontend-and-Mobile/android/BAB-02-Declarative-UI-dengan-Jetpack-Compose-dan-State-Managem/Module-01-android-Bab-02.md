# BAB 02 MODULE 01: DECLARATIVE UI DENGAN JETPACK COMPOSE & STATE MANAGEMENT

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend & Mobile Engineering (`03-Frontend-and-Mobile`)
*   **Track:** Android Enterprise Core Engine
*   **Topik Modul:** Declarative UI dengan Jetpack Compose & State Management
*   **Tingkat Kerumitan:** Advanced / Staff-Level Engineering
*   **Prasyarat:** Pemahaman mendalam tentang Kotlin Coroutines & Flow, Lifecycle Android OS, Arsitektur MVVM/MVI, serta mekanisme rendering UI klasik berbasis Android View Tree.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Mendekonstruksi Paradigma UI:** Menggantikan model imperatif mutasi DOM/View Tree (`findViewById`, `setText()`) dengan paradigma deklaratif murni berbasis transformasi fungsional state-to-UI ($f(State) \to UI$).
2.  **Menganalisis Siklus Runtime Compose:** Menguasai 3 fase eksekusi Jetpack Compose (*Composition*, *Layout*, dan *Drawing*) serta mekanisme kerja *Slot Table* dan *Composer*.
3.  **Menerapkan Pola State Management Deterministik:** Membangun alur data *Unidirectional Data Flow* (UDF) menggunakan `StateFlow`, `rememberSaveable`, dan *Custom Saver* yang tahan terhadap konfigurasi ulang sistem (*Configuration Change*) dan *Process Death*.
4.  **Mengoptimalkan Recomposition Melalui Stability System:** Mengaudit dan menegakkan stabilitas tipe data menggunakan anotasi `@Immutable` dan `@Stable` guna memitigasi *unnecessary recompositions* pada pohon komposisi berskala besar.
5.  **Menerapkan Hardening, Observabilitas, dan Performa Skala Produksi:** Memanfaatkan *Compose Layout Inspector*, compiler metrics, serta integrasi pelindung state berbasis arsitektur enterprise.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Mental Model: Dari Stateful Tree Mutation Menuju Pure Functional Projection

Dalam Android View System klasik (imperatif), komponen UI direpresentasikan sebagai objek kelas yang *stateful* (misalnya `TextView`, `RecyclerView`). Modifikasi tampilan dilakukan secara eksternal melalui instruksi eksplisit:

```
[Event Diterima] -> Controller Mengambil View -> Memanggil view.setText() -> View Memodifikasi State Internal -> View Meminta RequestLayout()
```

Kelemahan mendasar dari model ini adalah **State Fragmentation**: State riil aplikasi berada di ViewModel/Presenter, sedangkan View menyimpan representasi visual state-nya sendiri. Hal ini memicu risiko inkonsistensi (*state divergence*), kebocoran memori lifecycle, dan kondisi balapan (*race condition*).

Sebaliknya, **Jetpack Compose** mengadopsi mental model fungsional reaktif:

$$UI = f(State)$$

Fungsi `@Composable` bukanlah konstruktor objek tampilan visual, melainkan deskripsi struktur data runtime yang memproyeksikan data (*State*) menjadi representasi visual UI. Saat state berubah, fungsi tersebut dieksekusi ulang (*Recomposition*). 

```
[Event Diterima] -> State Dimutasi Secara Terpusat -> Engine Compose Menghitung Diff -> Node Terkait Di-render Ulang
```

Mental model kuncinya: **UI tidak memiliki state mandiri; UI hanyalah refleksi deterministik dari State pada satuan waktu tertentu.**

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Tiga Fase Jetpack Compose

Jetpack Compose memproses data menjadi pixel pada layar melalui pipeline pipeline tiga fase linier yang dioptimalkan:

```
+-----------------------------------------------------------------------------+
|                                STATE BERUBAH                                |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
| 1. COMPOSITION (Fase Eksekusi Fungsi Composable)                            |
|    - Engine membaca State snapshot.                                         |
|    - Mengeksekusi blok kode @Composable.                                    |
|    - Membangun/memperbarui "LayoutNode Tree" via Slot Table.                |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
| 2. LAYOUT (Fase Pengukuran & Penempatan)                                    |
|    - Mengukur dimensi setiap LayoutNode (Constraints -> MeasureResult).     |
|    - Menentukan koordinat relatif (X, Y) secara rekursif (Single Pass).     |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
| 3. DRAWING (Fase Render ke Canvas)                                          |
|    - Menerjemahkan LayoutNode menjadi instruksi Canvas (DrawScope).         |
|    - Mengirim perintah grafis ke RenderNode / hardware-accelerated pipeline.|
+-----------------------------------------------------------------------------+
```

### Arsitektur Alur Data: Unidirectional Data Flow (UDF)

Untuk mencegah divergensi data, arsitektur Compose memisahkan mutasi state dari pemanggilan UI dengan mekanisme UDF:

```
             +-----------------------------------------+
             |               ViewModel                 |
             |  - Memegang Single Source of Truth      |
             |  - Menjalankan logika bisnis            |
             +-----------------------------------------+
                       |                     ^
             StateFlow |                     | UI Events
             (Turun)   |                     | (Naik)
                       v                     |
             +-----------------------------------------+
             |            Composable Root              |
             |  - Mengonsumsi State via collectAsState |
             |  - Menghubungkan lambda handler event   |
             +-----------------------------------------+
                       |                     ^
             Props     |                     | Callbacks
             (Turun)   |                     | (Naik)
                       v                     |
             +-----------------------------------------+
             |         Leaf Composable (Stateless)     |
             |  - Hanya merender elemen visual dasar   |
             |  - Meneruskan interaksi via onAction()  |
             +-----------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Slot Table

Di balik layar, runtime Compose tidak menggunakan struktur *node tree* tradisional yang berat untuk merekam Composition. Sebaliknya, Compose mengimplementasikan struktur data linier berbasis array bernama **Slot Table** (serupa dengan konsep *Gap Buffer* pada text editor).

*   **Penyimpanan Runtun:** Slot Table menyimpan grup pemanggilan fungsi, parameter, dan nilai `remember` dalam satu array kontinu.
*   **Gap Pointer:** Penambahan atau pembaruan node menggeser *Gap* ke lokasi pemanggilan Composable, memungkinkan operasi penyisipan dan penghapusan bernilai amortisasi $O(1)$.
*   **Posisi Slot:** Composer melacak indeks eksekusi. Ketika indeks eksekusi membaca state yang tidak berubah, eksekusi melompati slot terkait (*Smart Recomposition / Skipping*).

### 2. Snapshot State System

Sistem state Compose diatur oleh subsistem `androidx.compose.runtime.snapshots.Snapshot`. Terinspirasi dari *Multiversion Concurrency Control* (MVCC) pada database:

*   **Isolated State Read/Write:** Setiap thread/proses membaca state dari snapshot terisolasi pada waktu tertentu.
*   **Snapshot Mutation:** Saat state `MutableState<T>` diubah, perubahan tersebut dicatat dalam snapshot lokal sebelum diterapkan (*commit*) ke snapshot global.
*   **Notification Loop:** Komit yang berhasil memicu notifikasi otomatis ke semua observer yang mencatat ketergantungan baca (*read dependency*) pada state tersebut, menandai node Compose terkait untuk dijadwalkan dalam recomposition berikutnya.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Sistem Stabilitas Tipe Data (Stability System)

Compose Compiler menyematkan inferensi metadata performa ke setiap kelas Kotlin saat kompilasi. Metadata ini menentukan apakah parameter Composable dapat dilewati (*skippable*) saat Recomposition:

1.  **Stable (`@Stable`):**
    *   Mengimplementasikan `equals` secara konsisten untuk dua instance yang sama.
    *   Jika properti publik berubah, sistem akan menerima sinyal notifikasi.
    *   Dua instance identik akan selalu mengembalikan nilai komparasi yang sama.
2.  **Immutable (`@Immutable`):**
    *   Seluruh properti publik berstatus `val` dan tipe datanya juga merupakan tipe *Immutable*.
    *   Instance dijamin tidak akan pernah berubah nilainya setelah instansiasi.
3.  **Unstable:**
    *   Kelas yang memiliki properti publik bertipe `var`, atau mengandung koleksi standar pustaka standar Kotlin (seperti `List<T>`, `Set<T>`, `Map<K, V>`).
    *   *Peringatan:* Mengapa `List<T>` dianggap Unstable? Karena di runtime, instance `List` dapat berupa mutasi tersembunyi (`java.util.ArrayList`), sehingga compiler tidak dapat menjamin immutabilitasnya tanpa memindai seluruh referensi memori.

Jika suatu fungsi `@Composable` menerima setidaknya satu parameter yang bertipe **Unstable**, engine Compose mematikan optimasi *skipping* pada Composable tersebut dan memaksanya untuk selalu di-*recompose* setiap kali parent-nya dieksekusi ulang.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi dasar pengelolaan state dengan *State Hoisting* dan proteksi siklus hidup.

```kotlin
package com.enterprise.compose.fundamental

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * Stateful Container: Bertanggung jawab menyimpan state lokal
 * dan menangani mutasi siklus hidup.
 */
@Composable
fun CounterStatefulContainer(modifier: Modifier = Modifier) {
    // State disimpan melintasi Recomposition dan Configuration Change
    var counter by rememberSaveable { mutableIntStateOf(0) }
    var note by rememberSaveable { mutableStateOf("") }

    CounterStatelessPresenter(
        counterValue = counter,
        noteValue = note,
        onIncrement = { counter++ },
        onNoteChange = { updatedNote -> note = updatedNote },
        modifier = modifier
    )
}

/**
 * Stateless Presenter: Memenuhi kaidah UDF murni.
 * Hanya menerima parameter data dan memancarkan aksi melalui lambda.
 */
@Composable
fun CounterStatelessPresenter(
    counterValue: Int,
    noteValue: String,
    onIncrement: () -> Unit,
    onNoteChange: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier.padding(16.dp)) {
        Text(text = "Nilai Counter: $counterValue")
        
        Button(
            onClick = onIncrement,
            modifier = Modifier.padding(top = 8.dp)
        ) {
            Text("Tambah Nilai")
        }

        OutlinedTextField(
            value = noteValue,
            onValueChange = onNoteChange,
            label = { Text("Catatan Mutasi") },
            modifier = Modifier.padding(top = 16.dp)
        )
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 24:** `var counter by rememberSaveable { mutableIntStateOf(0) }`
    *   `mutableIntStateOf(0)`: Mengalokasikan primitif snapshot state khusus tipe integer untuk mencegah overhead *boxing/unboxing*.
    *   `rememberSaveable`: Memasukkan data ke dalam Android `SavedStateHandle/Bundle` internal. Jika aktivitas dihancurkan akibat rotasi layar atau pembersihan memori latar belakang (*Process Death*), nilai `counter` otomatis direstorasi.
    *   `by`: Sintaksis *Property Delegate* yang menyederhanakan akses langsung ke nilai tanpa perlu eksplisit memanggil `.value`.
*   **Baris 40–46:** Deklarasi `CounterStatelessPresenter(...)`
    *   Menerapkan paradigma **State Hoisting**: Memisahkan komponen visual dari logika penyimpanan state.
    *   Komponen ini bersifat sepenuhnya deterministik dan mudah diuji secara modular (*isolated unit testing*), karena perilaku visualnya hanya dipengaruhi oleh nilai input parameternya.
*   **Baris 54:** `Button(onClick = onIncrement)`
    *   Menghindari modifikasi state secara langsung di dalam komponen anak. Sinyal klik diteruskan ke atas (*Event Up*) menuju kontainer stateful utama.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Sistem Transaksi Pembayaran Fintech (High-Concurreny & Audited State)

**Konteks Masalah:**
Sebuah aplikasi pembayaran digital berskala enterprise sering mengalami keluhan kritis:
1.  **Double-submission bug:** Pengguna menekan tombol "Bayar" berkali-kali secara simultan saat jaringan lambat, memicu tagihan ganda.
2.  **UI Flickering & Battery Drain:** Recomposition berlebihan merender ulang seluruh komponen transaksi setiap kali *countdown timer* diskon berdetik setiap detik.
3.  **Process Death Loss:** Ketika pengguna beralih ke aplikasi autentikator SMS/OTP pihak ketiga, Android OS menghentikan proses aplikasi karena tekanan memori (*low-memory kill*). Saat pengguna kembali, rincian pembayaran kosong dan proses transaksi gagal secara diam-diam.

**Solusi Desain Rekayasa:**
Membangun engine transaksi pembayaran berbasis arsitektur **MVI (Model-View-Intent)** yang terisolasi menggunakan immutable data wrappers, custom state savers untuk tipe data kompleks, serta penanganan event UI berbasis coroutine channel yang aman dari konkurensi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

```kotlin
package com.enterprise.compose.fintech

import android.os.Parcelable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import kotlinx.collections.immutable.ImmutableList
import kotlinx.collections.immutable.persistentListOf
import kotlinx.collections.immutable.toImmutableList
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.parcelize.Parcelize
import java.math.BigDecimal

// --- DOMAIN CONTRACTS & STATE CONTRACTS ---

@Parcelize
data class CurrencyAmount(
    val amount: BigDecimal,
    val currencyCode: String
) : Parcelable

@Immutable
data class TransactionItem(
    val id: String,
    val title: String,
    val fee: CurrencyAmount
)

sealed interface PaymentUiState {
    val items: ImmutableList<TransactionItem>
    val total: CurrencyAmount

    data class Idle(
        override val items: ImmutableList<TransactionItem>,
        override val total: CurrencyAmount
    ) : PaymentUiState

    data class Processing(
        override val items: ImmutableList<TransactionItem>,
        override val total: CurrencyAmount
    ) : PaymentUiState

    data class Success(
        override val items: ImmutableList<TransactionItem>,
        override val total: CurrencyAmount,
        val transactionReference: String
    ) : PaymentUiState
}

sealed interface PaymentSideEffect {
    data class ShowToast(val message: String) : PaymentSideEffect
    data class NavigateToReceipt(val txHash: String) : PaymentSideEffect
}

// --- ENTERPRISE VIEWMODEL ---

class PaymentEngineViewModel : ViewModel() {

    private val _uiState = MutableStateFlow<PaymentUiState>(
        PaymentUiState.Idle(
            items = persistentListOf(
                TransactionItem("TX-1", "Biaya Langganan Enterprise", CurrencyAmount(BigDecimal("450000.00"), "IDR")),
                TransactionItem("TX-2", "Pajak Pertambahan Nilai (PPN)", CurrencyAmount(BigDecimal("49500.00"), "IDR"))
            ),
            total = CurrencyAmount(BigDecimal("499500.00"), "IDR")
        )
    )
    val uiState: StateFlow<PaymentUiState> = _uiState.asStateFlow()

    private val _effectChannel = Channel<PaymentSideEffect>(Channel.BUFFERED)
    val effect = _effectChannel.receiveAsFlow()

    fun dispatchPaymentIntent() {
        val currentState = _uiState.value
        // Mutex/Lock guard terhadap double-submission
        if (currentState is PaymentUiState.Processing) return

        viewModelScope.launch {
            _uiState.update { 
                PaymentUiState.Processing(it.items, it.total) 
            }

            try {
                // Simulasi Network Call & Cryptographic Signing
                delay(2000)
                val reference = "REF-${System.currentTimeMillis()}"

                _uiState.update { 
                    PaymentUiState.Success(it.items, it.total, reference) 
                }
                _effectChannel.send(PaymentSideEffect.NavigateToReceipt(reference))
            } catch (t: Throwable) {
                _uiState.update { 
                    PaymentUiState.Idle(it.items, it.total) 
                }
                _effectChannel.send(PaymentSideEffect.ShowToast(t.localizedMessage ?: "Kegagalan Sistem"))
            }
        }
    }
}

// --- COMPOSE UI LAYER & CUSTOM SAVER ---

/**
 * Custom Saver untuk menangani preservasi state input dinamis (misal memo voucher).
 */
data class UserDraftNote(val note: String)

val UserDraftNoteSaver = Saver<UserDraftNote, String>(
    save = { it.note },
    restore = { UserDraftNote(it) }
)

@Composable
fun PaymentTransactionScreen(
    viewModel: PaymentEngineViewModel,
    modifier: Modifier = Modifier
) {
    // Collect lifecycle-aware: Mematikan konsumsi saat aplikasi berada di latar belakang
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    // Menggunakan custom saver untuk state lokal independen
    var draftNote by rememberSaveable(saver = UserDraftNoteSaver) {
        UserDraftNote("")
    }

    PaymentScreenContent(
        state = state,
        draftNote = draftNote,
        onDraftNoteChange = { draftNote = UserDraftNote(it) },
        onPayClicked = { viewModel.dispatchPaymentIntent() },
        modifier = modifier
    )
}

@Composable
private fun PaymentScreenContent(
    state: PaymentUiState,
    draftNote: UserDraftNote,
    onDraftNoteChange: (String) -> Unit,
    onPayClicked: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Ringkasan Pembayaran",
            style = MaterialTheme.typography.headlineMedium
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Render transaksi berbasis Immutable Collection
        TransactionList(items = state.items)

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = draftNote.note,
            onValueChange = onDraftNoteChange,
            label = { Text("Catatan Internal Akuntansi") },
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.weight(1f))

        Text(
            text = "Total: ${state.total.currencyCode} ${state.total.amount}",
            style = MaterialTheme.typography.titleLarge
        )

        Spacer(modifier = Modifier.height(12.dp))

        Button(
            onClick = onPayClicked,
            enabled = state !is PaymentUiState.Processing,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
        ) {
            if (state is PaymentUiState.Processing) {
                CircularProgressIndicator(
                    color = MaterialTheme.colorScheme.onPrimary,
                    modifier = Modifier.size(24.dp)
                )
            } else {
                Text(text = "Eksekusi Pembayaran")
            }
        }
    }
}

@Composable
private fun TransactionList(
    items: ImmutableList<TransactionItem>,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        items.forEach { item ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(text = item.title)
                Text(text = "${item.fee.currencyCode} ${item.fee.amount}")
            }
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Parameter | Jetpack Compose (Declarative) | Android View System (XML Imperative) |
| :--- | :--- | :--- |
| **Penyimpanan State** | Eksternal & Terpusat (ViewModel / Slot Table) | Terdesentralisasi di dalam atribut View masing-masing |
| **Siklus Hidup Rendering** | Recomposition dinamis berdasarkan state diffing | Mutasi manual via Layout/Draw traversal request |
| **Stabilitas Tipe Data** | Sangat sensitif; Tipe tidak stabil memicu *Over-recomposition* | Bebas batasan tipe Kotlin; Developer menangani mutasi secara manual |
| **Alokasi Memori** | Efisien berkat Slot Table linier, meminimalkan hierarki objek | Tinggi; Setiap node View mewarisi ratusan field kelas `View.java` |
| **Kurva Belajar** | Curam; Memerlukan pemahaman mendalam tentang eksekusi fungsional & compiler runtime | Landai; Model OOP tradisional yang memodifikasi properti instance |
| **Overhead Kompilasi** | Lebih lambat; Compiler plugin menyuntikkan instruksi Slot Table | Lebih cepat; Parsing XML hanya menghasilkan binding R.id |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Recomposition Loop Terjebak di Snapshot Writes:**
    *   *Edge Case:* Menulis ke `MutableState` langsung di dalam badan eksekusi fungsi `@Composable` tanpa proteksi event/effect:
        ```kotlin
        @Composable
        fun MalformedComponent() {
            var state by remember { mutableIntStateOf(0) }
            state++ // BAHAYA: Memicu infinite recomposition loop seketika!
        }
        ```
    *   *Mitigasi:* Seluruh mutasi state **hanya boleh** terjadi di dalam *callback event* (`onClick`) atau terisolasi di dalam coroutine effects (`LaunchedEffect`).
2.  **State Loss pada Dynamic Scaffolding:**
    *   *Edge Case:* Memindahkan composable di dalam hirarki menggunakan `if/else` dapat mengubah index key slot table secara dramatis. Hal ini menyebabkan runtime menganggap instance tersebut baru, mereset state `remember`.
    *   *Mitigasi:* Gunakan `key(identifier) { ... }` untuk mempertahankan identitas composable di dalam struktur dinamis, atau gunakan `rememberSaveable`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Standard Collections dalam UI State Interface
```kotlin
// KESALAHAN: Compose Compiler menganggap List sebagai Unstable
data class DashboardState(val users: List<User>)

// CARA BENAR: Gunakan Immutable Collections
import kotlinx.collections.immutable.ImmutableList

@Immutable
data class DashboardState(val users: ImmutableList<User>)
```

### 2. Menggunakan `collectAsState()` Bukan `collectAsStateWithLifecycle()`
```kotlin
// KESALAHAN: Membiarkan Flow tetap aktif saat aplikasi di background
val state by viewModel.state.collectAsState()

// CARA BENAR: Menghemat CPU dan baterai secara otomatis
val state by viewModel.state.collectAsStateWithLifecycle()
```

### 3. Membaca State di Luar Scope Minimal (State Reading Scope)
```kotlin
// KESALAHAN: Recomposition dipicu pada seluruh blok Column
@Composable
fun HeavyScreen(scrollOffset: MutableState<Int>) {
    Column(modifier = Modifier.offset(y = scrollOffset.value.dp)) { /*...*/ }
}

// CARA BENAR: Tunda pembacaan state hingga fase Layout/Draw via lambda modifier
@Composable
fun OptimalScreen(scrollOffset: MutableState<Int>) {
    Column(modifier = Modifier.offset { IntOffset(x = 0, y = scrollOffset.value) }) { /*...*/ }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Aturan Parameter Modifier:** Komponen `@Composable` modular wajib mengekspos parameter default `modifier: Modifier = Modifier` dan menempatkannya sebagai parameter opsional pertama.
2.  **Strict State Hoisting:** Komponen presentasional murni tidak boleh menginstansiasi ViewModel atau dependency injection (`hiltViewModel()`). ViewModel hanya boleh diinjeksi pada komponen tingkat root (*Screen level*).
3.  **Explicit Naming Event:** Hindari nama callback ambigu seperti `onAction()`. Gunakan nama yang mencerminkan intent pengguna, seperti `onConfirmPaymentClicked()` atau `onSearchQuerySubmitted()`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI

1.  **Fase Penundaan Pembacaan State (*Deferring State Reads*):**
    Jika suatu nilai state berubah pada frekuensi tinggi (misalnya scroll position atau data sensor), baca state tersebut langsung pada fase **Draw** menggunakan `Modifier.drawWithContent` atau lambda `Modifier.graphicsLayer { ... }`. Pendekatan ini sepenuhnya melewati fase **Composition** dan **Layout**, sehingga menghemat siklus instruksi CPU.
2.  **Derived State untuk Kalkulasi Intensif:**
    Gunakan `derivedStateOf` ketika suatu state diturunkan dari state lain yang sering berubah, namun hanya perlu memicu recomposition saat hasil akhirnya memenuhi kondisi tertentu:
    ```kotlin
    val showScrollToTopButton by remember {
        derivedStateOf { listState.firstVisibleItemIndex > 5 }
    }
    ```

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Pembersihan Data Sensitif dari Slot Table:**
    Hindari menyimpan data kredensial mentah (seperti PIN, CVV kartu kredit, atau kata sandi) dalam jangka panjang di dalam `remember` atau `rememberSaveable`. Snapshot state tersimpan di dalam memori heap, dan `rememberSaveable` menyalin data ke `SavedStateHandle` (yang dapat terekspos jika Android OS menulis state aktivitas ke disk saat memori rendah).
    *   *Hardening:* Bungkus data sensitif dalam wrapper sementara bertipe `CharArray` yang dapat ditimpa nilainya (*zeroized*) segera setelah digunakan, lalu hapus dari state terpusat.
2.  **Pencegahan Click-Jacking / UI Redressing:**
    Pasang *filter touch* keamanan di root Compose surface untuk mencegah eksploitasi *overlay tapjacking*:
    ```kotlin
    Modifier.pointerInput(Unit) {
        // Blok interaksi jika frame dideteksi terhalang oleh window lain
    }
    ```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Metrik Kompilasi (Compose Compiler Metrics)

Jalankan audit stabilitas kode secara otomatis via Gradle Compiler Plugin dengan menambahkan konfigurasi berikut:

```kotlin
// build.gradle.kts
tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
    compilerOptions {
        freeCompilerArgs.addAll(
            "-P", "plugin:androidx.compose.compiler.plugins.kotlin:reportsDestination=${layout.buildDirectory.asFile.get()}/compose_reports",
            "-P", "plugin:androidx.compose.compiler.plugins.kotlin:metricsDestination=${layout.buildDirectory.asFile.get()}/compose_metrics"
        )
    }
}
```

Analisis output file:
*   `<module>-classes.txt`: Memeriksa apakah kelas data Anda bertanda `stable` atau `unstable`.
*   `<module>-composables.txt`: Memeriksa apakah fungsi composable berstatus `skippable` atau `restartable`.

### Layout Inspector Telemetry
Gunakan **Android Studio Layout Inspector** untuk melacak Recomposition Counter:
*   Kolom **Recomposition Count**: Menampilkan berapa kali fungsi dipanggil ulang.
*   Kolom **Skipped Count**: Memvalidasi apakah optimasi pelewatan recomposition berhasil bekerja pada leaf nodes aplikasi Anda.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **$UI = f(State)$**: UI adalah proyeksi deterministik; jangan memutasi view secara imperatif.
*   **3 Fase**: Composition (membuat tree) $\to$ Layout (mengukur & memosisikan) $\to$ Draw (merender visual).
*   **Slot Table**: Struktur memori linier dengan Gap Buffer yang mengelola state Compose dan alur eksekusinya.
*   **State Hoisting**: Pindahkan state ke tingkat pemanggil (parent) untuk membuat komponen presentasional stateless, aman, dan mudah diuji.
*   **remember vs rememberSaveable**: `remember` hanya bertahan selama Recomposition; `rememberSaveable` bertahan melintasi *Configuration Change* dan *Process Death*.
*   **Stabilitas**: List standar bersifat *Unstable*. Gunakan `kotlinx.collections.immutable` atau tandai kelas wrapper dengan `@Immutable` untuk mengaktifkan fitur *smart skipping*.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa penggunaan parameter bertipe `java.util.List<T>` standar dapat menyebabkan fungsi `@Composable` kehilangan kemampuan *smart skipping* (tidak bisa di-skip saat recomposition)?
*   A. Karena `List` tidak memiliki method `equals` dan `hashCode`.
*   B. Karena Compose Compiler memperlakukan interface `List` publik sebagai tipe yang *unstable*, mengingat implementasi aslinya dapat dimutasi secara eksternal.
*   C. Karena compiler Compose hanya mendukung tipe data primitif untuk *smart skipping*.
*   D. Karena objek `List` otomatis dihapus oleh Garbage Collector saat fase layout.

### Soal 2
Perhatikan potongan kode berikut:
```kotlin
@Composable
fun DynamicHeader(scrollValue: State<Int>) {
    Text(
        text = "Dashboard",
        modifier = Modifier.padding(top = scrollValue.value.dp)
    )
}
```
Masalah performa apa yang terjadi, dan bagaimana solusinya?
*   A. Tidak ada masalah, implementasi tersebut sudah optimal.
*   B. Memicu memory leak; solusinya bungkus dengan `rememberSaveable`.
*   C. Membaca state pada fase Composition menyebabkan recomposition dipicu pada setiap perubahan pixel scroll; solusinya tunda pembacaan menggunakan lambda offset modifier.
*   D. Crash NullPointerException saat pertama kali dirender.

### Soal 3
Kapan sebaiknya Anda menggunakan `derivedStateOf` alih-alih mengevaluasi kondisi secara langsung di dalam Composable?
*   A. Hanya ketika memuat data asinkron dari REST API.
*   B. Saat state input sering berubah nilainya, namun UI hanya perlu dihitung ulang ketika hasil akhir pemrosesan memenuhi kriteria tertentu.
*   C. Saat data perlu disimpan melintasi *Process Death*.
*   D. Saat melakukan Dependency Injection di layer Composable.

### Soal 4
Apa perbedaan fundamental antara `remember` dan `rememberSaveable`?
*   A. `remember` menyimpan data di disk lokal, `rememberSaveable` di memori RAM.
*   B. `remember` hanya mempertahankan state selama recomposition aktif; `rememberSaveable` menyimpan state ke dalam Android Saved State registry untuk memulihkannya pasca-*process death* atau rotasi layar.
*   C. `remember` ditujukan khusus untuk Compose Desktop, sedangkan `rememberSaveable` untuk Compose Android.
*   D. Keduanya memiliki fungsi yang identik, `rememberSaveable` hanyalah alias usang (*deprecated*).

### Soal 5
Bagaimana cara sistem Snapshot Compose menangani pembacaan dan penulisan state secara konkuren?
*   A. Menggunakan penguncian global berbasis `synchronized` thread lock yang memblokir rendering.
*   B. Mematikan fitur multithreading dan menjalankan semua eksekusi state pada Main Thread secara linier.
*   C. Menggunakan pola arsitektur MVCC (Multiversion Concurrency Control) di mana mutasi dicatat pada snapshot terisolasi sebelum diterapkan ke snapshot global.
*   D. Menghapus state lama secara asinkron tanpa memverifikasi perubahan data.

---

### Kunci Jawaban & Analisis

1.  **Jawaban: B**
    *Analisis:* Secara default, compiler tidak dapat memastikan apakah implementasi `List` bersifat immutable atau mutable (seperti `ArrayList`). Demi menjaga konsistensi state dan mencegah UI usang (*stale*), Compose memperlakukan interface koleksi standar sebagai *unstable*, sehingga mematikan fitur skipping pada fungsi tersebut.
2.  **Jawaban: C**
    *Analisis:* Membaca `.value` di dalam pemanggilan parameter modifier `padding()` memaksa runtime merecompose fungsi `DynamicHeader` setiap kali pixel scroll berubah (60/120 kali per detik). Dengan menunda pembacaan ke fase layout menggunakan modifier berbasis lambda (seperti `Modifier.offset { ... }`), fase composition dapat dilewati sepenuhnya.
3.  **Jawaban: B**
    *Analisis:* `derivedStateOf` berfungsi sebagai filter penyangga redudansi recomposition. Fitur ini mengamati perubahan state yang frekuensinya tinggi, namun hanya memancarkan pembaruan state turunan ketika hasil ekspresinya berubah.
4.  **Jawaban: B**
    *Analisis:* `remember` mengalokasikan slot memori pada Slot Table siklus composition aktif saat ini. Begitu aktivitas dihancurkan dan dibuat ulang (*configuration change/process death*), Slot Table diinisialisasi dari awal. Sebaliknya, `rememberSaveable` mengintegrasikan nilai state ke dalam Android OS `Bundle` mechanism.
5.  **Jawaban: C**
    *Analisis:* Sistem Snapshot runtime Compose mengadaptasi filosofi MVCC database. Hal ini memungkinkan pembacaan state berlangsung non-blocking dan terisolasi dari proses penulisan yang sedang berjalan di background thread lain, sebelum akhirnya disinkronisasikan ke snapshot utama secara atomik.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Tantangan Rekayasa: Engine Transaksi Valuta Asing Real-Time (High-Frequency Trading Terminal)

#### Spesifikasi Kebutuhan Teknis:
1.  **Arsitektur State