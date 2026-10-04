# BAB 02: Quiz, Challenge, & Knowledge Check
**Declarative UI dengan Jetpack Compose & State Management**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Paradigma Pergeseran UI & Slot Table
Jelaskan perbedaan mendasar antara manipulasi *View Hierarchy* imperatif (Android Traditional View) dan evaluasi deklaratif pada Jetpack Compose. Bagaimana arsitektur *Slot Table* dan *Positional Memoization* pada Compose Compiler & Runtime memungkinkan *incremental recomposition* yang efisien tanpa membangun ulang seluruh pohon UI (*UI Tree*) dari nol?

### Soal 1.2: Unidirectional Data Flow (UDF) & State Hoisting Boundaries
Dalam arsitektur *Unidirectional Data Flow* (UDF), di mana batas (*boundary*) ideal untuk melakukan *State Hoisting*? Bandingkan konsekuensi arsitektural antara melakukan *hoisting* state ke level *Leaf Composable*, *Screen-level Composable*, hingga ke *AAC ViewModel*. Evaluasi dampaknya terhadap *reusability*, *testability*, dan *recomposition scope*.

### Soal 1.3: Daur Hidup State: `remember`, `rememberSaveable`, dan `ViewModel`
Bedakan siklus hidup dan lokasi alokasi memori dari:
1. `remember { mutableStateOf(...) }`
2. `rememberSaveable { mutableStateOf(...) }`
3. `val state by viewModel.state.collectAsStateWithLifecycle()`

Jelaskan skenario kegagalan spesifik (*failure mode*) pada masing-masing pendekatan ketika terjadi:
- *Recomposition* lokal.
- *Configuration change* (misal: rotasi layar).
- *System-initiated process death* (misal: memori ditekan oleh OS saat aplikasi di latar belakang).

### Soal 1.4: Model Efek Samping (Side-Effects Mechanics)
Mengapa pemanggilan fungsi penulisan (*side-effect*) langsung di dalam badan *Composable* dianggap sebagai *anti-pattern* fatal? Jelaskan siklus eksekusi, pembatalan (*cancellation*), dan *threading model* dari:
- `LaunchedEffect` (dan penanganan mutasi `key`).
- `rememberCoroutineScope`.
- `DisposableEffect`.
- `SideEffect`.

### Soal 1.5: Compose Compiler Stability System
Bagaimana Compose Compiler mengklasifikasikan tipe data menjadi *Stable*, *Immutable*, atau *Unstable*? Jelaskan mengapa penggunaan koleksi standar seperti `List<T>` dari Kotlin Standard Library secara *default* dianggap *unstable* oleh *compiler*, serta bagaimana kondisi ini memicu *unnecessary recompositions* pada Composable yang seharusnya *skippable*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Deferring State Reads Melalui 3 Fase Compose
Jetpack Compose mengeksekusi UI melalui tiga fase: *Composition*, *Layout*, dan *Drawing*. Analisis perbedaan performa antara kedua kode berikut saat `scrollOffset` berubah dengan frekuensi tinggi (misal: 60-120Hz):

```kotlin
// Pendekatan A
Modifier.offset(y = scrollOffset.value.dp)

// Pendekatan B
Modifier.offset { IntOffset(x = 0, y = scrollOffset.value.roundToInt()) }
```
Jelaskan fase mana yang diabaikan (*skipped*) oleh Pendekatan B dan mengapa hal tersebut mencegah *jank* pada *main thread*.

### Soal 2.2: Snapshot State Multiversion Concurrency Control (MVCC)
Sistem state Compose dibangun di atas model *Snapshot System* yang mengadaptasi konsep MVCC dari basis data. Jelaskan bagaimana Compose menangani skenario di mana dua *thread* berbeda membaca dan memodifikasi `MutableState` yang sama secara bersamaan. Apa peran dari `Snapshot.takeSnapshot()`, `Snapshot.sendApplyNotifications()`, dan bagaimana resolusi konflik diselesaikan?

### Soal 2.3: `derivedStateOf` vs `remember(key)`
Diberikan skenario sebuah `LazyListState`:
```kotlin
// Kasus 1
val showScrollToTop by remember(listState.firstVisibleItemIndex) {
    mutableStateOf(listState.firstVisibleItemIndex > 0)
}

// Kasus 2
val showScrollToTop by remember {
    derivedStateOf { listState.firstVisibleItemIndex > 0 }
}
```
Bongkar perbedaan mekanisme internal pemrosesan kedua kasus di atas saat pengguna melakukan *scrolling*. Kasus mana yang memicu *recomposition loop* atau *allocation churn*, dan kasus mana yang secara optimal memotong komputasi? Berikan justifikasi teknisnya.

### Soal 2.4: Coroutine Scope Leakage & Lifecycle Mismatch
Sebuah asynchronous task dijalankan menggunakan `rememberCoroutineScope()` untuk melakukan polling data jaringan yang dipicu oleh interaksi klik tombol. Namun, saat pengguna menekan tombol *Back* dan Composable keluar dari *Composition*, terjadi *crash* atau pemborosan memori.
1. Mengapa `rememberCoroutineScope` terikat pada *Composition lifecycle* dan bukan *Activity/Fragment lifecycle*?
2. Apa yang terjadi jika scope tersebut meluncurkan *coroutine* yang merujuk pada objek Composable lokal setelah Composable tersebut di-*dispose*?

### Soal 2.5: SubcomposeLayout Bottlenecks
Komponen seperti `LazyColumn` dan `BoxWithConstraints` menggunakan `SubcomposeLayout`. Jelaskan trade-off komputasi dari penundaan fase *composition* hingga fase *measurement*. Mengapa penggunaan `SubcomposeLayout` yang ceroboh pada komponen berulang skala besar dapat merusak performa *frame budget* (16ms / 8ms per frame)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Skala Besar (Frame Drop & UI Freezes pada Infinite Feed)
**Konteks Produksi:**
Aplikasi e-commerce enterprise mengalami degradasi performa berat (*frame rate* anjlok dari 120 FPS ke <30 FPS) pada halaman utama yang memuat `LazyColumn` berisi puluhan ribu produk interaktif. Berdasarkan *Layout Inspector*, setiap kali *countdown timer* diskon global (berdetik setiap 1 detik) diperbarui, **seluruh item** di dalam `LazyColumn` melakukan recomposition, meskipun data produk pada masing-masing item tidak berubah.

Data model produk didefinisikan sebagai berikut:
```kotlin
// Modul :core:model (Pure Kotlin/Java Module tanpa plugin Compose)
data class ProductDto(
    val id: String,
    val title: String,
    val tags: List<String>,
    val price: BigDecimal
)
```

**Pertanyaan Diagnostik & Solusi:**
1. Bedah akar penyebab mengapa item list tidak dapat di-*skip* oleh Compose Compiler. Analisis peran `ProductDto` (termasuk tipe `List<String>`) dan ketiadaan plugin Compose pada modul core.
2. Rancang strategi arsitektur konkret untuk membuat Composable item list bersifat `skippable` tanpa merusak arsitektur modular (*decoupling*) aplikasi.
3. Bagaimana cara Anda mengisolasi perubahan *state* dari timer global agar recomposition hanya terjadi pada komponen teks timer, tanpa menyentuh *parent layout* atau daftar produk di sekitarnya?

---

### Skenario B: Race Condition & Data Integrity (Multi-Step Checkout Form)
**Konteks Produksi:**
Pada form checkout multifase dengan validasi input intensif (alamat pengiriman, opsi kupon, dan metode pembayaran), pengguna mengetik secara cepat pada kolom kupon. Form mengonsumsi state dari `StateFlow` di ViewModel:

```kotlin
// ViewModel
val checkoutUiState: StateFlow<CheckoutUiState> = ...

fun onCouponChanged(coupon: String) {
    viewModelScope.launch {
        val isValid = validationRepository.validateCoupon(coupon) // Suspending async call
        _state.update { it.copy(coupon = coupon, isCouponValid = isValid) }
    }
}
```

**Insiden:**
Pengguna mengetik kode kupon `"DISCOUNT100"`. Namun, hasil akhir di UI menampilkan status bahwa kupon `"DISCOUNT100"` tidak valid, padahal respon API terakhir untuk `"DISCOUNT100"` valid. Log menunjukkan respons validasi untuk input parsial `"DISC"` selesai dieksekusi **setelah** respons `"DISCOUNT100"` tiba di klien, menimpa (*overwrite*) state final.

**Pertanyaan Diagnostik & Solusi:**
1. Identifikasi cacat konkurensi pada implementasi `onCouponChanged` di atas.
2. Rekonstruksi arsitektur penanganan *event* dan aliran data tersebut menggunakan operator Kotlin Flow yang tepat (seperti `flatMapLatest`, `conflate`, atau mekanisme mutasi atomik lainnya) untuk menjamin *eventual consistency* dan mencegah *out-of-order state overwrites*.
3. Bagaimana Anda memastikan UI tetap responsif (bebas *input lag*) saat pengetikan cepat, namun tidak melakukan *spamming* request ke backend service?

---

### Skenario C: Trade-off Desain Sistem (Arsitektur Ambient Context: CompositionLocal vs Hilt DI)
**Konteks Produksi:**
Arsitek tim Anda mengusulkan untuk menyimpan state analitik global, status autentikasi pengguna (*session token*), dan konfigurasi *dynamic theme* ke dalam `CompositionLocalProvider` di level root:

```kotlin
val LocalUserSession = compositionLocalOf<UserSession> { error("No session provided") }
val LocalAnalyticsManager = staticCompositionLocalOf<AnalyticsManager> { error("No manager") }
```

Sebagian tim senior menolak pendekatan ini dan bersikeras bahwa dependensi ini harus diinjeksi secara eksplisit menggunakan Hilt ke dalam masing-masing ViewModel layar.

**Pertanyaan Diagnostik & Evaluasi Arsitektural:**
1. Analisis implikasi performa antara `compositionLocalOf` vs `staticCompositionLocalOf`. Apa dampak langsung terhadap pohon Composable jika nilai di dalam `LocalAnalyticsManager` bermutasi?
2. Buat matriks evaluasi (skala: Dampak Performa, Testing Overhead, Arsitektur Decoupling, Traceability Bug) antara menggunakan **CompositionLocal** vs **Scoped ViewModel Injection (Hilt)** untuk dependensi state di atas.
3. Kapan penggunaan `CompositionLocal` dapat dibenarkan secara arsitektur enterprise, dan kapan penggunaannya dikategorikan sebagai *anti-pattern* penyembunyian dependensi (*service locator hidden dependency*)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Real-Time Crypto Order Book & Depth Chart Engine
**Deskripsi Masalah:**
Anda diminta membangun komponen real-time *Crypto Order Book* (daftar order jual/beli) dan *Depth Visualizer* yang terhubung ke live WebSocket stream. Sistem menerima pembaruan delta state harga hingga 60 kali per detik (60 updates/sec). Implementasi dasar menyebabkan UI mengalami *severe freezing*, alokasi GC (Garbage Collection) yang masif, dan konsumsi memori tinggi karena Composable merekonstruksi daftar UI pada setiap event WebSocket.

### Requirements:
1. **Zero-Jank Stream Processing:**
   - Konsumsi data stream dengan kemampuan membuang (*drop*) atau menggabungkan (*conflate*) state jika rendering thread belum siap, tanpa memblokir thread penerima socket.
   - Gunakan `collectAsStateWithLifecycle` dengan konfigurasi lifecycle yang tepat untuk menghentikan pemrosesan saat aplikasi di-background.
2. **Phase-Specific State Reading (Deferred Reads):**
   - Visualisasi grafik *depth* (Canvas bar chart horizontal) tidak boleh memicu fase *Recomposition* saat ukuran bar berubah. Perubahan bar hanya boleh memicu fase *Drawing*.
3. **Optimized Structural Stability:**
   - Seluruh model data stream harus strictly stable/immutable tanpa memicu mutasi instansiasi list baru yang memicu recomposition di seluruh baris tabel.
4. **Target Performa:**
   - Pertahankan konsisten 60-120 FPS pada perangkat low-end (e.g., Pixel 3a / setara chipset entry-level).
   - Compose compiler metrics harus memvalidasi item baris tabel sebagai `restartable` dan `skippable`.

### Constraints:
- Dilarang menggunakan *Third-Party Charting Library*. Wajib native Jetpack Compose UI (`Canvas`, custom `Layout`, atau lambda modifiers).
- Alokasi memori objek (object allocations) di dalam fungsi *Canvas draw phase* harus bernilai **0 (Zero Allocation)** untuk mencegah GC Thrashing.
- Implementasi tidak boleh menelan thread utama (*Main Thread*). Parsing JSON/Payload WebSocket harus diisolasi di `Dispatchers.Default`.

### Expected Output:
1. **Data Contract & Architecture Definition:**
   - Kode deklarasi Immutable Model dengan anotasi stabilitas yang tepat.
   - ViewModel yang mengelola transformasi WebSocket Flow menjadi UI State dengan backpressure handling.
2. **Composable Implementation:**
   - Composable `OrderBookScreen` dan `OrderBookRow` dengan isolasi pembacaan state via lambda modifiers.
   - Implementasi `Canvas` untuk rendering depth bar horizontal dengan memanfaatkan `drawWithCache` atau akses koordinat langsung tanpa alokasi objek Paint/Path di setiap render pass.
3. **Compose Compiler Metrics Report Simulation:**
   - Tunjukkan cuplikan ekspektasi output text dari file metrics Compose compiler (stabilty file) yang membuktikan bahwa Composable Anda berstatus:
     ```text
     restartable skippable scheme("[androidx.compose.ui.UiComposable]") fun OrderBookRow(...)
     ```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme kerja Compose Compiler, IR (Intermediate Representation) manipulation, dan pembuatan *Slot Table*.
- [ ] Tiga fase pemrosesan frame pada Compose: *Composition*, *Layout*, dan *Drawing*, serta titik pemanggilan pembacaan state (*state read tracking*).
- [ ] Aturan inferensi stabilitas tipe data oleh Compose Compiler (`@Stable`, `@Immutable`, primitif, fungsionalitas lambda vs *method reference*).
- [ ] Perbedaan fundamental antara `derivedStateOf` (mereduksi recomposition) dan `remember(keys)` (mereduksi kalkulasi).
- [ ] Snapshot State System, mutasi atomik, dan model memori multithreading di balik `MutableState`.
- [ ] Mekanisme siklus hidup efek samping Compose (`LaunchedEffect`, `DisposableEffect`, `SideEffect`, `produceState`).
- [ ] Arsitektur SubcomposeLayout beserta penalti performanya jika disalahgunakan.

### Saya tidak perlu menghafal:
- [ ] Kode byte (bytecode) spesifik yang di-generate oleh Compose Compiler plugin.
- [ ] Nilai bitmask internal yang digunakan oleh runtime Slot Table untuk menandai state slots.
- [ ] Seluruh parameter opsional default dari setiap komponen Material Design 3.
- [ ] Sintaks exact dari flag command line konfigurasi Gradle metrics compiler (cukup tahu cara mencari dan mengaktifkannya saat audit performa).

### Saya harus bisa melakukan:
- [ ] Menjalankan dan menganalisis **Compose Compiler Metrics** (`enableCompilerMetrics` / `enableCompilerReports`) untuk mendeteksi *unstable classes* dan *non-skippable composables*.
- [ ] Menggunakan **Android Studio Layout Inspector** untuk memverifikasi *Recomposition Counts* dan mendiagnosis anomali *Skipped Counts*.
- [ ] Mengoptimalkan Composable yang lambat dengan memindahkan pembacaan state dari fase *Composition* ke fase *Layout* (`Modifier.layout`, `Modifier.offset { ... }`) atau fase *Drawing* (`Modifier.drawWithCache`, `Modifier.drawBehind`).
- [ ] Membungkus atau memetakan (*mapping*) DTO dari modul eksternal yang *unstable* menjadi UI Model yang sepenuhnya *Stable/Immutable*.
- [ ] Merancang state machine UDF yang aman terhadap *race conditions* dan *configuration changes* menggunakan Kotlin StateFlow dan Channels.