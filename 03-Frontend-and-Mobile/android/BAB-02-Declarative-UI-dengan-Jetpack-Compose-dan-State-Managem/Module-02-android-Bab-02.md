# Kurikulum Enterprise Android Engineering
## Bab 02: Declarative UI dengan Jetpack Compose & State Management
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal/Senior Android Engineer diharapkan mampu:
- **Menganalisis dan Membedah Internal Compiler & Runtime Compose**: Memahami transformasi Abstract Syntax Tree (AST) oleh Compose Compiler Plugin, injeksi parameter `$composer`, pembuatan node pada *Slot Table* (Gap Buffer), serta mekanisme *Snapshot State System* (MVCC).
- **Mengoptimalkan Fase Rendering Compose**: Mengisolasi eksekusi pada 3 fase utama (*Composition*, *Layout*, *Draw*) guna menekan recomposition cascades dan mempertahankan frame budget 120 FPS (< 8.33ms per frame).
- **Merancang Custom Layout Tingkat Lanjut**: Mengimplementasikan `Layout` kustom dan `SubcomposeLayout` dengan performa deterministik untuk use-case dinamis tanpa alokasi memori berlebih.
- **Menerapkan Stability Contract Skala Enterprise**: Mengaudit kestabilan tipe data melalui *Compose Compiler Metrics*, mengeliminasi *unstable lambdas*, dan mengintegrasikan `kotlinx.collections.immutable`.
- **Membangun Arsitektur UDF (Unidirectional Data Flow) Skala Besar**: Menghubungkan ViewModel, Coroutines, StateFlow, dan Compose UI dengan isolasi side-effect (`LaunchedEffect`, `rememberCoroutineScope`, `produceState`) yang thread-safe dan lifecycle-aware.

---

### 2. Prerequisite
- **Mahir Bahasa Kotlin**: Pemahaman mendalam tentang *inline classes*, *lambdas with receiver*, *delegated properties*, dan Coroutines/Flow.
- **Konsep Dasar Jetpack Compose**: Mengetahui deklarasi `@Composable`, modifier dasar, dan state primitives (`remember`, `mutableStateOf`).
- **Android Architecture Components**: Pemahaman Lifecycle-aware components, ViewModels, dan Clean Architecture patterns.
- **Profil Performa**: Pengalaman dasar dengan Android Studio Profiler, Layout Inspector, dan Perfetto/Systrace.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Compose Compiler Transformation & The Slot Table
Compose bukan sekadar *library*; ini adalah runtime dan compiler plugin terpadu. Ketika fungsi dianotasi dengan `@Composable`, Compose Compiler melakukan *type transformation*:

1. **Parameter Injection**: Menambahkan parameter sintetis `$composer: Composer` dan bitmask `$changed: Int` ke dalam signature fungsi:
   ```kotlin
   // Source Code
   @Composable fun StatusBadge(text: String) { ... }
   
   // Transformed Bytecode Representation (Conceptual)
   fun StatusBadge(text: String, $composer: Composer, $changed: Int) { ... }
   ```
2. **Control Flow Analysis via Bitmask**: Parameter `$changed` membawa informasi dependensi state dari parent. Bitmask dievaluasi secara biner: jika bit menunjukkan data tidak berubah dan *stability contract* terpenuhi, seluruh blok fungsi di-*skip*.
3. **The Slot Table (Gap Buffer)**:
   Runtime Compose menggunakan struktur data *Slot Table*, diimplementasikan dengan strategi *Gap Buffer* (serupa dengan algoritma pada text editor emacs). Slot Table menyimpan cache pohon komposisi (calls, state, modifiers, child nodes).
   - Saat Recomposition terjadi, reader dan writer traversing tabel ini.
   - Jika terdapat penambahan atau perubahan node, "Gap" digeser ke lokasi tersebut untuk melakukan mutasi lokal secara $O(1)$ amortized tanpa merelokasi keseluruhan memori.

```
+--------------------------------------------------------------------------+
|                        Compose Slot Table (Gap Buffer)                  |
+--------------------------------------------------------------------------+
| [Group: App] | [Group: Header] | [State: user] |    GAP (Free Memory)    |
| (Read Index)                   | (Write Index) | [====== UNUSED ======]  |
+--------------------------------------------------------------------------+
|                          ... [Group: ContentList] | [Group: Footer] ...  |
+--------------------------------------------------------------------------+
```

#### 3.2 Snapshot State System (Multiversion Concurrency Control - MVCC)
Jetpack Compose mengadopsi model konkurensi database (MVCC) untuk manajemen state melalui `Snapshot`:
- Pembacaan variabel `State<T>` di dalam blok Composition secara otomatis direkam ke dalam *Snapshot aktif*.
- Ketika variabel `MutableState<T>` ditulis, Compose menandai state tersebut *dirty* dan mengirimkan notifikasi ke runtime via `Snapshot.sendApplyNotifications()`.
- Thread safety dijamin: modifikasi state di thread latar belakang (background snapshot) dapat diisolasi dan di-*merge* ke global snapshot melalui atomic commit operations. Jika terjadi konflik tulis, commit dibatalkan atau diselesaikan menggunakan strategi penanganan konflik (*merge policy*).

#### 3.3 The Three Phases of Jetpack Compose
Compose mengeksekusi UI rendering dalam tiga fase linier yang independen:

```
[ State Change ]
       │
       ▼
┌──────────────────┐
│ 1. Composition   │ ── Evaluasi fungsi @Composable. Pohon UI (LayoutNode) dibangun/diperbarui.
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ 2. Layout        │ ── Pengukuran (Measure) & Penempatan (Place). Menghasilkan ukuran & koordinat.
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ 3. Drawing       │ ── Render piksel ke layar via Skia Canvas (DrawScope).
└──────────────────┘
```

*Optimasi Kunci*: Pembacaan state harus ditunda (*deferred*) ke fase paling lambat yang memungkinkan. Jika state frekuensi tinggi (contoh: offset scroll) dibaca pada fase **Composition**, seluruh composable di-*recompose*. Jika ditunda ke fase **Layout** (menggunakan lambda `Modifier.layout` atau `Modifier.offset { ... }`), fase Composition dilewati. Jika ditunda ke fase **Draw** (`Modifier.drawWithContent`), Composition dan Layout dilewati secara penuh.

#### 3.4 Stability System & Strong Skipping Mode
Compiler mengklasifikasikan semua tipe parameter ke dalam dua kategori:
- **Stable**: Data tipe primitif, `String`, kelas dengan semua properti publik `val` bertipe primitif/stabil, atau tipe yang dianotasi `@Immutable`/`@Stable`.
- **Unstable**: Antarmuka (*interface*), kelas pihak ketiga di luar project Compose, atau kelas dengan properti `var` publik, serta Standard Collections (`List`, `Map`, `Set`). Parameter *unstable* selalu memicu recomposition paksa karena compiler tidak dapat memvalidasi kesamaan objek secara struktural saat runtime.

*Strong Skipping Mode* (default di Kotlin 2.0+): Compose Compiler mengaktifkan perlakuan skipping bahkan untuk composable dengan parameter unstable via *instance equality check* ($===$, referensial) dan secara otomatis membungkus unstable lambdas dengan `remember`.

---

### 4. Why & What

| Dimensi Arsitektur | View System Tradisional (XML) | Jetpack Compose Enterprise |
| :--- | :--- | :--- |
| **Model Paradigma** | Imperatif (`findViewById`, mutating setter). | Deklaratif & Fungsional (UI = $f(State)$). |
| **State Synchronization** | Rentan terhadap *Split-brain state* (State ada di UI dan di Business Logic). | *Single Source of Truth* (SSOT) strictly enforced via UDF. |
| **Pohon Rendering** | Mutasi langsung pada `View` hierarchy node tree yang berat. | Virtual UI Tree (`LayoutNode`) yang dipetakan secara efisien di Slot Table. |
| **Custom Components** | Inheritance (`extends ViewGroup`, override `onMeasure`, `onLayout`, `onDraw`). | Komposisi murni (`Layout`, `SubcomposeLayout`) berbobot ringan (*flat hierarchy*). |
| **Overhead Context** | Berat, butuh binding ke `android.content.Context` pada tiap instansiasi view. | Bebas dependensi konteks platform langsung; rendering terisolasi via Canvas Skia. |

Mengapa memahami arsitektur internal krusial bagi enterprise?
Dalam aplikasi skala besar (misal: FinTech, E-Commerce), rendering lists dengan ribuan elemen, real-time streaming tickers, atau animasi kompleks akan menghasilkan *jank* (drop frames) parah jika recomposition cascade terjadi di thread UI. Pengembang enterprise harus tahu persis **kapan** mengalokasikan memori dan **fase mana** yang mengeksekusi state.

---

### 5. How (Workflow Detail)

Alur kerja propagasi State-to-Pixel pada Enterprise Compose Architecture:

```
[User Interaction / WebSocket Push]
               │
               ▼
[Domain / Presentation Logic (ViewModel)]
               │ Updates (Immutable State Flow)
               ▼
   [StateFlow<UiState> emitted]
               │ Collected via collectAsStateWithLifecycle()
               ▼
    [Snapshot State Change]
               │
   ┌───────────┴───────────┐
   │ Is State read in      │
   │ Composition Phase?    │
   └───────────┬───────────┘
               ├─────────────────────────────────────────┐
             [YES]                                     [NO]
               │                                         │
               ▼                                         ▼
   [Recompose Scope Executed]              ┌───────────────────────────┐
   - Check bitmask changed flags           │ Is State read in          │
   - Skip stable parameters                │ Layout Phase?             │
   - Update Slot Table Gap Buffer          └─────────────┬─────────────┘
               │                                         ├──────────────┐
               ▼                                       [YES]           [NO]
   [Layout Phase: Measure & Place] ◄─────────────────────┘              │
   - Constraints pass (Min/Max Width/Height)                            │
   - Custom Alignment & Offsets calculated                              │
               │                                                        │
               ▼                                                        ▼
   [Draw Phase: Canvas Paint Operations] ◄──────────────────────────────┘
   - Direct execution on Skia Canvas
   - Zero object allocation per frame
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Slot Table: Tape Recorder Head & Typewriter Gap
Bayangkan Slot Table sebagai pita rekaman audio multi-track (atau Gap Buffer teks editor). 
- Setiap kali Anda memanggil Composable child, Compose "merekam" token dan referensinya ke pita.
- Ketika ada perubahan (contoh: conditional composable `if (showExtra) ExtraContent()`), runtime menggeser *Gap* (ruang kosong fleksibel) tepat ke titik percabangan tersebut.
- Penulisan konten baru dilakukan langsung di Gap tanpa harus memindahkan elemen-elemen di belakang pita secara utuh satu per satu.

#### Diagram: Recomposition Boundary Isolation

```
RootComposable
 ├── HeaderComponent (Stable params -> SKIPPED)
 ├── DynamicTickerContainer (Recomposition Boundary Scope)
 │    │
 │    ├── [State Read Happens Here: tickerState]
 │    │    └── Text(tickerState.price)  <-- HANYA NODE INI DI-RECOMPOSE
 │    │
 │    └── StaticIcon() (No state read -> SKIPPED)
 └── FooterComponent (Stable params -> SKIPPED)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Deferred State Read Menggunakan Lambda Modifiers
Membedakan pembacaan state langsung vs pembacaan ditunda (*deferred*) untuk mencegah recomposition loop saat scrolling:

```kotlin
// BURUK: Recomposition dijalankan setiap piksel scroll berubah (60-120x per detik)
@Composable
fun BadScrollAwareHeader(scrollOffsetState: State<Int>) {
    Box(
        modifier = Modifier
            .offset(y = (scrollOffsetState.value / 2).dp) // Recomposition phase read!
            .fillMaxWidth()
            .height(56.dp)
            .background(Color.Blue)
    )
}

// BAIK: Fase Composition dilewati secara penuh, eksekusi langsung di Fase Layout
@Composable
fun OptimizedScrollAwareHeader(scrollOffsetProvider: () -> Int) {
    Box(
        modifier = Modifier
            .offset { IntOffset(x = 0, y = scrollOffsetProvider() / 2) } // Layout phase read!
            .fillMaxWidth()
            .height(56.dp)
            .background(Color.Blue)
    )
}
```

#### 7.2 Practical Example: High-Throughput Real-Time Order Book Engine
Implementasi komponen list enterprise dengan custom measuring logic, kestabilan eksplisit, dan isolasi recomposition:

```kotlin
package com.enterprise.trading.ui.orderbook

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.collections.immutable.ImmutableList
import java.math.BigDecimal

// Contract data model strictly immutable
@Immutable
data class OrderBookEntry(
    val price: BigDecimal,
    val quantity: BigDecimal,
    val cumulativePercentage: Float // 0.0f - 1.0f
)

@Immutable
data class OrderBookUiState(
    val asks: ImmutableList<OrderBookEntry>,
    val bids: ImmutableList<OrderBookEntry>
)

@Composable
fun OrderBookRow(
    entry: OrderBookEntry,
    isBid: Boolean,
    modifier: Modifier = Modifier
) {
    val barColor = if (isBid) Color(0x2600C853) else Color(0x26D50000)
    
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(24.dp)
    ) {
        // Draw depth bar directly in Draw Phase - zero recomposition overhead
        Canvas(modifier = Modifier.fillMaxSize()) {
            val barWidth = size.width * entry.cumulativePercentage
            val startX = if (isBid) 0f else size.width - barWidth
            
            drawRect(
                color = barColor,
                topLeft = Offset(x = startX, y = 0f),
                size = Size(width = barWidth, height = size.height)
            )
        }

        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = entry.price.toPlainString(),
                color = if (isBid) Color(0xFF00C853) else Color(0xFFD50000),
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace
            )
            Text(
                text = entry.quantity.stripTrailingZeros().toPlainString(),
                color = Color.White,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace
            )
        }
    }
}
```

---

### 8. Real World Case Study: Enterprise SuperApp Dynamic Checkout Sheet

#### Latar Belakang & Masalah
Sebuah platform SuperApp logistik & finansial dengan 10+ juta Daily Active Users (DAU) mengalami *frame dropping* masif (jank mencapai 38% pada perangkat low-to-mid tier) saat pengguna berinteraksi dengan Dynamic Checkout Sheet. 

**Akar Masalah (Root Cause Analysis)**:
1. Model data `CheckoutUiState` menggunakan tipe `java.util.List` bawaan, menyebabkan Compiler menandai parameter model sebagai *unstable*. Akibatnya, setiap micro-update (misal: penghitungan estimasi ongkir real-time via background socket) memicu *recomposition cascade* pada seluruh pohon UI Checkout.
2. Penggunaan `Modifier.clickable` standar mengalokasikan objek baru (`Indication`, `InteractionSource`) di dalam loop daftar voucher belanja.
3. Total dropped frames: > 45 frames per scroll gesture (ANR warnings di Firebase Performance).

#### Solusi Arsitektur
1. **Refactoring ke Immutable Collections**:
   Mengganti representasi list dengan `kotlinx.collections.immutable.PersistentList`.
2. **Implementasi `derivedStateOf`**:
   Mengekstrak kalkulasi rumit diskon + pajak agar tidak dijalankan ulang di setiap recomposition parent.
3. **Komposisi Custom Layout via `SubcomposeLayout`**:
   Untuk floating summary bar yang ukurannya harus mengikuti dimensi dinamis content sheet secara adaptif tanpa double-pass measurement latency.

#### Implementasi Solusi Produksi

```kotlin
package com.enterprise.checkout.ui

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.SubcomposeLayout
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import kotlinx.collections.immutable.PersistentList

@Immutable
data class CartItem(val id: String, val title: String, val price: Long)

@Immutable
data class CheckoutState(
    val items: PersistentList<CartItem>,
    val appliedCouponRate: Float,
    val shippingFee: Long
)

@Composable
fun OptimizedCheckoutEngine(
    state: CheckoutState,
    modifier: Modifier = Modifier
) {
    // Derived state prevents recalculation unless internal dependencies strictly change
    val calculatedTotal by remember(state.items, state.appliedCouponRate, state.shippingFee) {
        derivedStateOf {
            val subtotal = state.items.sumOf { it.price }
            val discount = (subtotal * state.appliedCouponRate).toLong()
            (subtotal - discount) + state.shippingFee
        }
    }

    // Adaptive height measurement using enterprise SubcomposeLayout
    AdaptiveSummaryLayout(
        mainContent = {
            Column(modifier = Modifier.fillMaxWidth()) {
                state.items.forEach { item ->
                    key(item.id) { // Stable node identification in Slot Table
                        Text(text = "${item.title}: Rp ${item.price}", modifier = Modifier.padding(8.dp))
                    }
                }
            }
        },
        stickyFooter = {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(text = "Total Pembayaran:")
                Text(text = "Rp $calculatedTotal")
            }
        },
        modifier = modifier
    )
}

@Composable
fun AdaptiveSummaryLayout(
    mainContent: @Composable () -> Unit,
    stickyFooter: @Composable () -> Unit,
    modifier: Modifier = Modifier
) {
    SubcomposeLayout(modifier = modifier) { constraints ->
        // Subcompose main content first to measure height consumption
        val mainPlaceables = subcompose(SlotsEnum.Main, mainContent).map {
            it.measure(constraints.copy(minHeight = 0))
        }
        val mainHeight = mainPlaceables.sumOf { it.height }

        // Subcompose footer based on remaining or required space
        val footerPlaceables = subcompose(SlotsEnum.Footer, stickyFooter).map {
            it.measure(constraints.copy(minHeight = 0))
        }
        val footerHeight = footerPlaceables.sumOf { it.height }

        val layoutWidth = constraints.maxWidth
        val layoutHeight = (mainHeight + footerHeight).coerceAtMost(constraints.maxHeight)

        layout(layoutWidth, layoutHeight) {
            var yOffset = 0
            mainPlaceables.forEach {
                it.placeRelative(0, yOffset)
                yOffset += it.height
            }
            footerPlaceables.forEach {
                it.placeRelative(0, layoutHeight - footerHeight)
            }
        }
    }
}

private enum class SlotsEnum { Main, Footer }
```

**Hasil Metrik Pasca Implementasi**:
- *Dropped frame rate* anjlok dari **38%** menjadi **1.2%**.
- Alokasi memori GC berkurang sebesar **64%** selama interaksi checkout.

---

### 9. Trade-offs (Analisis Keputusan Teknikal)

| Pendekatan / Teknik | Keuntungan (Pros) | Biaya Teknis & Batasan (Cons / Trade-offs) |
| :--- | :--- | :--- |
| **`SubcomposeLayout`** | Memungkinkan subkomposisi bertingkat di mana pengukuran anak kedua bergantung pada hasil pengukuran anak pertama secara dinamis. | **Latensi Performa**. Membatalkan optimasi single-pass measurement Compose. Tidak boleh digunakan di dalam looping item berfrekuensi tinggi (misal: cell pada LazyColumn). |
| **`derivedStateOf`** | Memangkas Recomposition jika hasil kalkulasi akhir sama meskipun frekuensi state input tinggi (e.g., scroll threshold). | Menambah overhead alokasi memory object wrapper `DerivedSnapshotState` dan pencatatan dependency graph. Gunakan hanya jika komputasi lebih mahal dari alokasi tersebut. |
| **`Immutable Collections`** | Menjamin compiler stability skip secara absolut, mencegah cascade recomposition. | Membutuhkan dependensi library external (`kotlinx.collections.immutable`). Operasi modifikasi collection berbasis struktural copy memiliki overhead memori vs mutasi in-place array murni. |
| **Defensive Wrapper Class (`@Immutable`)** | Memaksa compiler menandai library/third-party DTOs sebagai stable tanpa perlu mapping manual ke UI data model. | Menyembunyikan bug konkurensi jika engineer melanggar kontrak dengan memasukkan field mutable di dalam class beranotasi tersebut. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Membaca Snapshot State di Root Composable Tanpa Boundary Scope
```kotlin
// ERROR KRITIS: Membaca animasi/scroll langsung di composable scope terluar
@Composable
fun ParentScreen(scrollState: ScrollState) {
    // Membaca scrollState.value di sini memaksa ParentScreen dan SELURUH anaknya
    // recompose setiap ada pergeseran 1 pixel.
    val alpha = if (scrollState.value > 100) 1f else 0.5f
    
    Header(modifier = Modifier.alpha(alpha))
    HeavyContentList()
}

// PERBAIKAN: Gunakan lambda modifier atau drawScope
@Composable
fun ParentScreen(scrollState: ScrollState) {
    Header(
        modifier = Modifier.graphicsLayer {
            // Evaluasi ditunda ke Phase 3: Draw Phase
            this.alpha = if (scrollState.value > 100) 1f else 0.5f
        }
    )
    HeavyContentList() // Terisolasi aman dari Recomposition
}
```

#### 10.2 Ketidakstabilan Akibat Instansiasi Lambda Inline
Jika Composable menerima parameter lambda yang mereferensikan variabel lokal tanpa `remember`, referensi instance lambda baru dibuat di setiap eksekusi, merusak validasi kesamaan (*equality check*):
```kotlin
// MASALAH: Instansiasi callback baru di setiap Recomposition
ItemRow(onClick = { viewModel.selectItem(item.id) })

// SOLUSI: Strong Skipping Mode (Kotlin 2.0+) atau bungkus dengan remember
val onSelect = remember(item.id) { { viewModel.selectItem(item.id) } }
ItemRow(onClick = onSelect)
```

#### 10.3 Troubleshooting Table

| Gejala Masalah | Investigasi (Debug Tool) | Resolusi |
| :--- | :--- | :--- |
| UI Mengalami Jank saat scroll LazyColumn | Layout Inspector: Recomposition Counter bertambah ribuan kali | Evaluasi stabilitas model data via *Compose Compiler Metrics*. Bungkus generic `List` menjadi `ImmutableList`. |
| Memory Leak saat rotasi layar | Memory Profiler: Instansiasi CoroutineScope tetap hidup | Ganti `rememberCoroutineScope()` untuk task async background panjang dengan lifecycle-aware side-effects (`LaunchedEffect` terikat key). |
| Data UI tidak terupdate saat model bermutasi | Snapshot tracking break | Properti data class bermutasi secara internal (`var` internal list). Ganti mutasi objek dengan instansiasi instance baru secara fungsional (`copy()`). |

---

### 11. Best Practices (Production Checklist)

#### Pre-Release Enterprise Checklist
- [ ] **Compiler Metrics Audited**: Periksa laporan output `-Pplugin:androidx.compose.compiler.plugins.kotlin:reportsDestination`. Pastikan 100% data class domain UI berstatus `stable`.
- [ ] **Zero Unstable Collections**: Tidak ada `java.util.*` collections atau interface standar `List<T>` terekspos langsung di parameter composable publik tanpa wrapper `@Immutable` atau `ImmutableList`.
- [ ] **Deferred State Phase**: Pembacaan posisi koordinat, offset, scrolling, dan nilai transisi animasi menggunakan overload lambda (`Modifier.offset { ... }`, `Modifier.graphicsLayer { ... }`).
- [ ] **Keyed Dynamic Collections**: Semua perulangan dinamis (`LazyColumn`, `items`, `for-loops`) memiliki parameter `key` unik dan deterministik, tidak bergantung pada indeks array.
- [ ] **No Side-Effects in Pure Composition Body**: Tidak menjalankan operasi non-idempotent (analytics tracking, database read, network call) di dalam flow eksekusi utama composable. Wajib diisolasi di `LaunchedEffect` atau lifecycle callbacks.
- [ ] **R8 / ProGuard Optimization**: Menjaga integritas annotation Compose Metadata dan memastikan release builds mengaktifkan full-mode R8 shrinking.

---

### 12. Hands-on Practice

Buat dan simpan struktur project di path: `hands-on/m02/`

#### Step 1: Inisialisasi Dependensi Enterprise (`hands-on/m02/build.gradle.kts`)
Tambahkan immutable collections dan compiler metrics flag:
```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.enterprise.handson.m02"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.enterprise.handson.m02"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }

    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-collections-immutable:0.3.8")
}

// Konfigurasi Compose Compiler Metrics untuk build release/debug
tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile> {
    compilerOptions {
        freeCompilerArgs.addAll(
            "-P",
            "plugin:androidx.compose.compiler.plugins.kotlin:reportsDestination=${project.layout.buildDirectory.asFile.get().absolutePath}/compose_metrics",
            "-P",
            "plugin:androidx.compose.compiler.plugins.kotlin:metricsDestination=${project.layout.buildDirectory.asFile.get().absolutePath}/compose_metrics"
        )
    }
}
```

#### Step 2: Implementasi Custom SubcomposeLayout (`hands-on/m02/src/main/java/com/enterprise/handson/m02/DynamicBadgeLayout.kt`)
Bangun custom layout yang mengukur lebar dinamis badge teks untuk menyesuaikan trailing icon layout secara presisi:

```kotlin
package com.enterprise.handson.m02

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.SubcomposeLayout
import androidx.compose.ui.unit.Constraints

@Composable
fun ProportionalBadgeContainer(
    mainContent: @Composable () -> Unit,
    badgeContent: @Composable () -> Unit,
    modifier: Modifier = Modifier
) {
    SubcomposeLayout(modifier = modifier) { constraints ->
        // 1. Measure main content
        val mainPlaceables = subcompose("main", mainContent).map {
            it.measure(constraints)
        }
        val mainWidth = mainPlaceables.maxOfOrNull { it.width } ?: 0
        val mainHeight = mainPlaceables.maxOfOrNull { it.height } ?: 0

        // 2. Measure badge without overflowing parent constraints
        val badgePlaceables = subcompose("badge", badgeContent).map {
            it.measure(
                Constraints(
                    maxWidth = (constraints.maxWidth - mainWidth).coerceAtLeast(0),
                    maxHeight = mainHeight
                )
            )
        }
        val badgeWidth = badgePlaceables.maxOfOrNull { it.width } ?: 0

        val totalWidth = (mainWidth + badgeWidth).coerceIn(constraints.minWidth, constraints.maxWidth)
        val totalHeight = mainHeight.coerceIn(constraints.minHeight, constraints.maxHeight)

        // 3. Placement phase
        layout(totalWidth, totalHeight) {
            var currentX = 0
            mainPlaceables.forEach {
                it.placeRelative(currentX, 0)
                currentX += it.width
            }
            badgePlaceables.forEach {
                it.placeRelative(currentX, (totalHeight - it.height) / 2)
            }
        }
    }
}
```

#### Step 3: Verifikasi Komposisi & Metrics
Eksekusi task Gradle pada terminal untuk memvalidasi output compiler metrics:
```bash
./gradlew assembleRelease
# Periksa file build/compose_metrics/app_release-classes.txt
```
Pastikan seluruh node UI ditandai dengan:
`class ProportionalBadgeContainer: stable`

---

### 13. Exercise

#### Level: Easy
Diberikan composable data model berikut:
```kotlin
data class UserNotification(
    var id: String,
    val title: String,
    val metadata: Map<String, String>
)
```
**Tugas**: Ubah struktur kelas di atas agar 100% stabil (*stable & skippable*) berdasarkan aturan stabilitas compiler Compose tanpa mengorbankan fungsionalitas data.

#### Level: Medium
Buat sebuah custom `Layout` (jangan gunakan `SubcomposeLayout`) dengan nama `FlowRowSimple`. Layout ini mengukur child nodes secara berurutan; jika penambahan node melebihi batas constraint `maxWidth`, tempatkan node berikutnya di baris (*row*) baru secara dinamis.

#### Level: Hard
Rancang komponen chart visualizer data transaksi keuangan secara virtual:
Komponen menerima data stream 1000 titik data per detik via `SharedFlow`. 
Implementasikan mekanisme rendering yang:
1. Tidak melakukan Recomposition lebih dari 60 kali per detik.
2. Tidak mengalokasikan objek baru pada heap di setiap frame render.
3. Menjalankan plotting seluruhnya pada fase **Draw** melalui integrasi `drawWithCache`.

---

### 14. Challenge (Tantangan Kompleks Enterprise)

#### Konteks Studi Kasus
Perusahaan logistik global memiliki sistem visualisasi armada interaktif. Layar harus menampilkan peta koordinat flat berskala besar dengan 2.000+ truk bergerak secara real-time via koneksi streaming MQTT/gRPC. 

#### Tantangan Arsitektur:
1. **Zero Garbage Collection Stutters**: Alokasi objek baru saat rendering marker berjalan wajib = 0 byte per delta frame.
2. **Dynamic Level of Detail (LoD)**: Ketika zoom-level kamera berubah, node truk yang berdekatan harus di-merge secara visual menjadi cluster badge dalam waktu kurang dari 5ms.
3. **Strict Constraints**: 
   - Dilarang menggunakan platform maps bawaan (Google Maps / Mapbox SDK); Canvas harus digambar murni via Compose `Canvas` / `DrawScope`.
   - Menggunakan `SubcomposeLayout` dilarang keras pada render loop utama.
   - Wajib mendesain custom state container dengan memanfaatkan *Snapshot mutation lock-free concurrency*.

*Delivery Requirement*: Serahkan rancangan arsitektur kelas data, state holder pattern, dan implementasi pipeline rendering custom Modifier-nya tanpa menimbulkan jank pada frame trace Systrace (120 FPS continuous budget).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Kapan tepatnya parameter `$changed` bitmask diinjeksi ke dalam signature fungsi `@Composable`?
   - A. Saat kompilasi Kotlin IR (Intermediate Representation) oleh Compose Compiler Plugin.
   - B. Saat runtime Android OS classloader memuat DEX file.
   - C. Saat fungsi `setContent {}` dieksekusi di Activity.
   - D. Diinjeksi oleh Dagger/Hilt saat proses dependency injection.

2. Struktur data utama yang digunakan oleh runtime Jetpack Compose untuk mengelola tree cache memori adalah:
   - A. Doubly Linked List
   - B. Red-Black Binary Tree
   - C. Gap Buffer (Slot Table)
   - D. Hash Map Table

3. Apa konsekuensi teknis jika kita membaca state `val scroll = remember { mutableStateOf(0) }` langsung di dalam body `@Composable` tanpa lambda modifier?
   - A. Tidak ada dampak performa sama sekali.
   - B. Seluruh fungsi composable tersebut akan dieksekusi ulang pada fase Composition di setiap perubahan nilai.
   - C. Terjadi compile-time error karena state tidak boleh dibaca di composition.
   - D. Nilai state otomatis di-cache dan tidak memperbarui UI.

4. Manakah tipe data koleksi di bawah ini yang dianggap sepenuhnya **Stable** secara native oleh Compose Compiler?
   - A. `java.util.ArrayList<T>`
   - B. `kotlin.collections.List<T>`
   - C. `kotlinx.collections.immutable.ImmutableList<T>`
   - D. `kotlin.collections.MutableList<T>`

5. Mengapa anotasi `@Immutable` dapat memicu rendering bug jika disalahgunakan oleh engineer?
   - A. Membuat aplikasi crash dengan `IllegalStateException`.
   - B. Compiler mempercayai developer dan mengabaikan pengecekan perubahan; jika objek sebenarnya bermutasi, UI tidak akan ter-refresh.
   - C. Anotasi tersebut otomatis menghapus objek dari Slot Table secara permanen.
   - D. Menjadikan memori CPU leak karena instansiasi berulang.

---

#### Bagian 2: Intermediate (Analisis Singkat)

6. Jelaskan perbedaan mendasar antara fase **Layout** dan fase **Composition** pada arsitektur pipeline Compose!
7. Mengapa penggunaan `SubcomposeLayout` di dalam body item `LazyColumn` sangat dihindari untuk standard production code?
8. Bagaimana cara kerja fungsi `derivedStateOf` dalam mereduksi frekuensi recomposition pada state bertipe counter frekuensi tinggi?
9. Apa perbedaan esensial antara lifecycle scope `LaunchedEffect(key)` vs `rememberCoroutineScope()`?
10. Sebutkan fungsi dari tool *Compose Compiler Metrics* dan dua metrik utama yang dihasilkannya!

---

#### Bagian 3: Enterprise Case Scenarios

11. **Skenario 1**: Tim Anda merilis fitur live stock market ticker. UI dibangun menggunakan `LazyColumn`. Setiap data websocket masuk (10x/detik), seluruh list mengalami recomposition meski hanya 1 baris ticker yang angkanya berubah. Analisis 2 potensi sumber kebocoran performa ini dan tuliskan resolusi arsitekturnya!
12. **Skenario 2**: Dalam sebuah form dinamis super panjang, terdapat logic validasi form yang kompleks di View Model. Terjadi freeze (ANR threshold mendekati 5 detik) saat user mengetik cepat pada `TextField`. Mengapa Snapshot state system dapat mengalami bottleneck pada skenario konkurensi data masif seperti ini, dan bagaimana solusinya?
13. **Skenario 3**: Sebuah custom component `DynamicMediaCanvas` membutuhkan pengukuran layout yang bergantung pada aspect ratio video stream yang berubah secara asinkron. Bagaimana Anda merancang layout pass agar tidak memicu `IllegalStateException: Measurement loop detected`?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. **A** — Plugin Compose Compiler mencegat tahap IR lowering pada pipeline kompilasi Kotlin untuk menyisipkan `$composer` dan `$changed`.
2. **C** — Runtime Compose menggunakan Gap Buffer (Slot Table) untuk menyediakan operasi insert/delete cache tree secara amortized $O(1)$.
3. **B** — Pembacaan state secara direct memicu eksekusi ulang keseluruhan scope Composition tempat ia dibaca.
4. **C** — Standard Kotlin `List` adalah interface, sehingga compiler menganggapnya unstable secara default. Hanya implementasi persistent/immutable immutable library yang dipetakan sebagai stable.
5. **B** — Janji kontrak `@Immutable` membuat compiler melewati verifikasi mutasi. Jika properti internal berubah tanpa membuat objek baru, slot table melewatkan recomposition (UI macet).

#### Bagian 2: Intermediate
6. **Composition** menentukan *komponen apa* yang ada pada UI tree (mengeksekusi composable functions & membangun LayoutNodes). **Layout** menentukan *ukuran* (Measure) dan *posisi* (Place) koordinat XY dari node-node yang telah terbentuk tersebut.
7. `SubcomposeLayout` menunda komposisi sub-tree sampai fase pengukuran tiba, membatalkan optimasi layout single-pass. Dalam `LazyColumn` yang sudah mengelola komposisi virtualnya sendiri, nested subcomposition menyebabkan frame budget terlampaui seketika.
8. `derivedStateOf` bertindak sebagai buffer; ia merekam dependensi state dinamis berfrekuensi tinggi (misal: scroll offset pixel demi pixel), namun hanya memancarkan notifikasi perubahan recomposition jika **hasil akhir** komputasi/predikat logikanya berubah (misal: `scrollOffset > 100`).
9. `LaunchedEffect` diluncurkan secara otomatis dari dalam fase Composition dan dibatalkan (*cancelled*) saat key berubah atau composable meninggalkan Composition Tree. `rememberCoroutineScope` mengikat scope ke Composable life, namun peluncuran coroutine-nya harus dipicu oleh event eksternal (misal: user klik tombol).
10. Mengekstrak auditibilitas performa kode Compose:
    - *classes.txt*: Mendiagnosis apakah kelas data berstatus `stable` atau `unstable`.
    - *composables.txt*: Menandai composable berstatus `skippable` vs `restartable only`.

#### Bagian 3: Production Case Solutions
11. **Penyebab**: 
    - Objek model tidak memiliki `@Immutable`/menggunakan `java.util.List` sehingga tiap item dianggap unstable.
    - Tidak menyertakan `key = { item.id }` di dalam `items()` DSL, menyebabkan LazyList mencocokkan item berdasarkan indeks array alih-alih identitas unik.
    **Resolusi**: Bungkus state list ke `PersistentList`, tandai model sebagai `@Immutable`, dan definisikan key deterministik pada `items(items = state.tickers, key = { it.symbol })`.
12. **Analisis**: Modifikasi state beruntun di main thread memicu Snapshot applying storm dan komputasi validasi berat di jalur thread yang sama.
    **Resolusi**: Pindahkan business logic validasi form ke background Coroutine (`Dispatchers.Default`) menggunakan flow operators seperti `debounce(300ms)` sebelum mengubah backing state Snapshot yang terikat ke UI.
13. **Resolusi**: Hindari mutasi nilai `MutableState` di dalam blok `Layout` measure policy secara rekursif. Gunakan `Modifier.aspectRatio` yang dihitung dari constraint parent atau pisahkan pembacaan ukuran aspect ratio menggunakan intrinsic measurements (`IntrinsicSize.Min`/`Max`).

---

### 16. Summary

```
                      JETPACK COMPOSE ENTERPRISE RUNTIME
                                       │
      ┌────────────────────────────────┼────────────────────────────────┐
      │                                │                                │
      ▼                                ▼                                ▼
COMPILER INTERNALS             THREE-PHASE PIPELINE             STABILITY CONTRACT
- IR Lowering Stage           1. Composition Phase              - Strong Skipping Mode
- Parameter $composer            (Build UI Tree)                - kotlinx.collections.immutable
- Bitmask $changed            2. Layout Phase                   - Deferred Execution
- Slot Table (Gap Buffer)        (Measure & Place)              - Single-pass Measurement
                              3. Draw Phase                     - Zero Object Allocations
                                 (Render to Skia)
```

Arsitektur Compose enterprise menuntut developer beralih dari sekadar paradigma *"UI yang berfungsi"* menuju *"UI dengan efisiensi komputasi deterministik"*. Performa 120 FPS tercapai dengan mengisolasi pembacaan Snapshot State ke fase paling akhir (Layout/Draw), menstabilkan kontrak struktur data via Immutable collections, serta memahami batasan komputasi runtime seperti Slot Table dan Gap Buffer. Penguasaan aspek-aspek internal ini adalah fondasi dalam membangun UI aplikasi mobile kelas dunia yang skalabel, bebas jank, dan stabil.