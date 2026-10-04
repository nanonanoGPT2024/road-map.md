# Bab 09: Performance Profiling, Memory Leaks, dan Benchmarking
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis siklus hidup alokasi memori pada Android Runtime (ART), mekanisme kerja *Concurrent Copying* (CC) Garbage Collector, serta interaksi kernel Linux melalui *Low Memory Killer Daemon* (`lmkd`).
- Menemukan, mengisolasi, dan memitigasi kebocoran memori (*memory leaks*) kompleks (termasuk *static reference retention*, *coroutine scope leakage*, *listener detachment failure*, dan *JNI/NDK native allocations*) menggunakan Shark Engine dan Android Studio Memory Profiler.
- Menginstrumentasikan automasi deteksi regresi performa berbasis Jetpack Macrobenchmark dan Microbenchmark ke dalam *Continuous Integration* (CI) pipeline.
- Mengonfigurasi dan memvalidasi *Baseline Profiles* serta *Startup Profiles* untuk mengeliminasi kompilasi Just-In-Time (JIT) pada jalur kritis (*critical user journey*), guna mencapai metrik Cold Start < 500ms dan *frame rendering* stabil pada 60/120 FPS.
- Mengoperasikan Perfetto CLI dan SQL queries untuk mengekstrak metrik *Jank*, *Choreographer dropped frames*, dan *RenderThread pipeline bottlenecks* pada skala produksi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Core Android Architecture**: Lifecycle `Activity`, `Fragment`, `ViewModel`, serta internal mekanisme `ViewTreeLifecycleOwner`.
- **Modern Concurrency**: Kotlin Coroutines (`CoroutineScope`, `Job`, `Dispatchers`), StateFlow, SharedFlow, serta struktur *structured concurrency*.
- **OS & Runtime Fundamentals**: Arsitektur Linux process memory model (`VSS`, `RSS`, `PSS`, `USS`), paging, heap vs. stack, serta dynamic linking (`.so` / JNI).
- **Tooling**: Kemampuan dasar menggunakan Android Studio Profiler (CPU, Memory, Network) dan eksekusi perintah via Android Debug Bridge (`adb`).

---

### 3. Concept & Internal Architecture

#### 3.1 ART (Android Runtime) Garbage Collection Internals
Android Runtime (ART) menggunakan kolektor memori utama bertipe **Concurrent Copying (CC)**. Karakteristik internal CC GC mencakup:
- **Compaction**: Mengurangi fragmentasi heap dengan memindahkan objek aktif (*live objects*) ke ruang memori yang bersebelahan (*contiguous space*) tanpa memerlukan *full-heap pause* yang panjang.
- **Read Barrier**: ART menyisipkan instruksi tingkat mesin (*hardware read barrier*) di setiap pembacaan referensi objek. Jika objek berada di area memori lama (*from-space*), read barrier secara atomik mereturn alamat baru objek di *to-space*.
- **Generational Concurrent Copying (GenCC)**: Diperkenalkan secara matang pada Android 10+, memisahkan heap menjadi *Young Generation* (objek berumur pendek) dan *Old Generation*. Alokasi baru masuk ke Young Generation yang dipindai secara berkala melalui minor collections, menghemat konsumsi siklus CPU hingga 30-40% dibanding non-generational CC.

```
+-------------------------------------------------------------------------+
|                              ART HEAP SPACE                             |
|  +-----------------------------------+-------------------------------+  |
|  |       Young Gen (Nursery)         |     Old Gen (Tenured Space)   |  |
|  |  [Obj A] [Obj B] [Free Chunk]     |   [Surviving Obj C] [Obj D]   |  |
|  +-----------------------------------+-------------------------------+  |
|  +-----------------------------------+-------------------------------+  |
|  |     Large Object Space (LOS)      |      Zygote & Non-Moving      |  |
|  |  [Bitmaps / ByteArrays > 12KB]    |   [Classes, ArtFields, JNI]   |  |
|  +-----------------------------------+-------------------------------+  |
+-------------------------------------------------------------------------+
```

Jika alokasi memori melebihi kapasitas dan memicu GC berturut-turut (*thrashing*), thread aplikasi (*main thread*) dapat mengalami *pause* sementara (*Stop-the-World phase* untuk penandaan akar referensi), yang termanifestasi sebagai **Jank** (frame drop).

#### 3.2 Linux Kernel, oom_score_adj, dan lmkd
Android tidak menggunakan *swap partition* konvensional seperti distribusi Linux desktop, melainkan **zRAM** (kompresi RAM berbasis swap swap-space terkompresi). Ketika tekanan memori fisik meningkat, kernel Linux dan *Low Memory Killer Daemon* (`lmkd`) bertindak:
1. `lmkd` memantau level tekanan memori via `vmpressure` event atau Kernel PSI (*Pressure Stall Information*).
2. Setiap proses Android diberi nilai `oom_score_adj` (rentang `-1000` hingga `1000`) oleh `ActivityManagerService` (AMS).
   - Foreground App (Active UI): `oom_score_adj = 0`
   - Visible App / Bound Service: `oom_score_adj = 100 - 200`
   - Previous App (Backstack): `oom_score_adj = 700`
   - Cached / Empty Process: `oom_score_adj = 900 - 999`
3. Ketika ambang batas (*watermark*) memori terlewati, `lmkd` mengirim sinyal `SIGKILL` (bukan `SIGTERM`) ke proses dengan `oom_score_adj` tertinggi. Objek heap tidak dibersihkan secara elegan; seluruh PID dimusnahkan seketika.

#### 3.3 UI Rendering Pipeline: Choreographer, HWUI, dan SurfaceFlinger
Sistem grafis Android beroperasi pada interval refresh rate monitor (contoh: 60Hz = 16.6ms, 120Hz = 8.33ms):
- **Choreographer**: Menerima sinyal hardware VSYNC. Menjadwalkan callbacks dalam urutan terstruktur: `CALLBACK_INPUT` -> `CALLBACK_ANIMATION` -> `CALLBACK_TRAVERSAL` (`measure`, `layout`, `draw`).
- **HWUI (Hardware UI Library)**: Mengonversi perintah kanvas 2D Android menjadi operasi Direct Rendering Command / Vulkan / OpenGL ES. Memiliki thread khusus yaitu **RenderThread**.
- **SurfaceFlinger**: Service sistem level rendah yang bertindak sebagai komposer. Mengambil buffer grafis dari berbagai layer aplikasi melalui antarmuka `BufferQueue` dan menyerahkannya ke Hardware Composer (HWC) untuk di-push ke panel layar.

```
[VSYNC Pulse] 
   │
   ▼
[Main Thread]    ──(Measure/Layout/Draw)──> [Sync Frame Data]
                                                    │
                                                    ▼
[RenderThread]   ──────(Issue GPU Ops)──────> [Render via Vulkan/GL]
                                                    │
                                                    ▼
[BufferQueue]    ───(Enqueue GraphicBuffer)─> [SurfaceFlinger] ──> [Display]
```

Jank terjadi bila waktu pemrosesan di **Main Thread + RenderThread > Interval VSYNC**.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional / Reaktif | Pendekatan Enterprise / Proaktif |
| :--- | :--- | :--- |
| **Pendeteksian Memory Leak** | Bergantung pada laporan Crashlytics saat terjadi `OutOfMemoryError` (OOM) di produksi. | Integrasi Shark/LeakCanary di staging/debug builds, headless memory assertion di end-to-end tests. |
| **Analisis Performa Rendering** | Pengujian manual (*scrolling feel*) di perangkat high-end milik developer. | CI-driven Macrobenchmark dengan pengujian metrik *Frame Timing Metric* (P50, P90, P99) di perangkat low-tier. |
| **Optimasi Cold Start** | Menunda inisialisasi SDK via Coroutines `Dispatchers.IO` tanpa struktur profil. | Implementasi *Baseline Profiles* dan *Startup Profile*, memangkas JIT compilation overhead secara deterministik. |
| **Tracing Bottleneck** | Menggunakan logcat timestamp manual (`System.currentTimeMillis()`). | AndroidX Tracing API terintegrasi dengan Perfetto custom counter & trace slice analysis via SQL. |

#### Mengapa Metrik P95/P99 Lebih Kritis Dibanding Rata-Rata (Mean)?
Dalam komputasi performa UI, nilai rata-rata (*average frame rate*) menipu tim engineering. Sebuah aplikasi yang berjalan pada 118 FPS selama 9 detik namun mengalami pembekuan (*freeze*) total selama 1 detik (0 FPS) akan menghasilkan rata-rata ~106 FPS. Namun, pengguna merasakan aplikasi tersebut rusak atau *lagging*. Metrik **P99 Frame Duration** mendeteksi 1% frame terburuk yang merusak persepsi kelancaran (*smoothness*).

---

### 5. How (Workflow Detail)

Alur kerja investigasi performa dan mitigasi degradasi sistematis:

```
[Mulai: Isu Performa / Crash Terdeteksi]
                  │
                  ▼
  [Apakah Masalah Terkait Memori / OOM?]
     ├── YA ──> Tangkap HPROF Snapshot via Android Studio Profiler / Dump Shark
     │           │
     │           ▼
     │         Identifikasi Dominator Tree: Cari Retained Size terbesar
     │           │
     │           ▼
     │         Lacak Jalur Referensi GC Root Terpendek (Shortest Path to GC Root)
     │           │
     │           ▼
     │         Terapkan Perbaikan: Putuskan Siklus Referensi / Lifecyle Unbinding
     │
     └── TIDAK ──> [Apakah Masalah Terkait Cold Start / Frame Drop (Jank)?]
                     │
                     ▼
                   Rekam Systrace / Perfetto Trace via Macrobenchmark Pipeline
                     │
                     ▼
                   Query Tracing Data: Periksa Main Thread Lock Contention & HWUI sync
                     │
                     ▼
                   Terapkan Optimasi: Baseline Profile, Lazy Initialization, Flatten View Tree
                     │
                     ▼
                   Validasi Regresi: Eksekusi Macrobenchmark via Gradle Managed Devices (GMD)
```

1. **Capture**: Ambil baseline profile dan trace memory heap (`.hprof`) atau runtime slices (`.perfetto-trace`).
2. **Isolate**: Tentukan GC Root penahan memori menggunakan dominator tree, atau identifikasi trace slice yang melebihi batas 16.6ms/8.3ms.
3. **Refactor**: Rekayasa ulang pemanggilan dependensi, hilangkan referensi *cross-lifecycle*, atau terapkan compilations profile.
4. **Automate**: Kunci ambang batas degradasi (contoh: max cold startup time = 650ms) pada level automated test.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengelolaan Dapur Restoran Bintang Lima

Bayangkan ART Memory Management dan Rendering Pipeline sebagai dapur restoran:
- **Heap Space**: Meja preparasi dapur.
- **Young Gen**: Meja potong sementara untuk bahan yang cepat dibuang (kulit bawang, plastik pembungkus).
- **Old Gen**: Meja saji dan penyimpanan panci utama.
- **Garbage Collector (CC GC)**: Petugas kebersihan yang membersihkan meja tanpa menghentikan koki memasak, kecuali saat harus memindahkan panci besar secara mendadak (*Stop-The-World pause*).
- **Memory Leak**: Asisten koki menyimpan catatan pesanan lama yang sudah selesai di atas meja utama dan terus menaruh piring kotor di atasnya. Meja menjadi penuh, dapur kehabisan tempat kerja, memicu **OOM (Out Of Memory)**.
- **Choreographer**: Bel pesanan yang berbunyi teratur setiap 8.3 milidetik.
- **Jank / Dropped Frame**: Bel berbunyi, namun koki masih memotong daging karena pisau tumpul (I/O di Main Thread); makanan telat disajikan ke pelayan.

#### Diagram: Dominator Tree & GC Root Retaining Pathway

```
              [ GC ROOT ]
        (App Scope Singleton)
                  │
                  ▼
           [NetworkManager]
                  │
                  ▼
           [EventListener] <── (Listener tidak di-unregister)
                  │
                  ▼
      [CheckoutActivity$Callback]
                  │
                  ▼
         [CheckoutActivity]  <── (Leaked Activity: Harus dimusnahkan oleh OS)
          │             │
          ▼             ▼
     [ViewTree]   [LargeBitmap] (12 MB uncompressed ARGB_8888)
          │
          ▼
   [CustomAdapter]
```
Jika `NetworkManager` mempertahankan `EventListener`, seluruh pohon objek ke bawah (`CheckoutActivity`, `ViewTree`, `LargeBitmap`) tertahan di RAM dan tidak dapat direklamasi oleh GC.

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Deteksi Leak Berbasis Coroutine & Lifecycle

Kasus umum: Meluncurkan Coroutine dengan lifecycle yang salah, menahan referensi konteks UI.

```kotlin
// Anti-Pattern: Mengikat coroutine ke GlobalScope atau Scope mandiri yang meloloskan Activity
class LeakyActivity : AppCompatActivity() {

    private val customScope = CoroutineScope(Dispatchers.Main + Job())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_leaky)

        customScope.launch {
            // Suspensi tak terbatas / polling loop
            while (true) {
                delay(1000)
                // Mempertahankan implisit referensi ke 'this' (LeakyActivity)
                findViewById<TextView>(R.id.txt_status).text = "Time: ${System.currentTimeMillis()}"
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        // KESALAHAN FATAL: customScope.cancel() TIDAK dipanggil!
        // LeakyActivity hancur di layar, tetapi Job coroutine terus berjalan di memory.
    }
}
```

```kotlin
// Production Pattern: Lifecycle-Aware Concurrency
class SafeActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_safe)

        // Solusi: Menggunakan lifecycleScope terikat secara native ke siklus hidup LifecycleOwner.
        // Saat onDestroy dipicu, Job dibatalkan otomatis via CancellationException.
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                while (isActive) {
                    delay(1000)
                    findViewById<TextView>(R.id.txt_status).text = "Time: ${System.currentTimeMillis()}"
                }
            }
        }
    }
}
```

#### 7.2 Practical Example: Enterprise Custom Benchmark, Shark Leak Assertions, & Tracing

Berikut adalah implementasi skala industri untuk Macrobenchmark pipeline, baseline profile capture, serta Shark Core programmatic heap parsing untuk automated regression test.

##### File: `benchmark/src/main/java/com/enterprise/benchmark/StartupMacrobenchmark.kt`
```kotlin
package com.enterprise.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.ExperimentalMetricApi
import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.TraceSectionMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
@LargeTest
class StartupMacrobenchmark {

    @get:Rule
    val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun measureStartupColdWithBaselineProfiles() = measureStartup(
        CompilationMode.Partial(
            baselineProfileMode = androidx.benchmark.macro.BaselineProfileMode.Require
        )
    )

    @Test
    fun measureStartupColdNoCompilation() = measureStartup(
        CompilationMode.None()
    )

    @OptIn(ExperimentalMetricApi::class)
    private fun measureStartup(compilationMode: CompilationMode) {
        benchmarkRule.measureRepeated(
            packageName = "com.enterprise.app",
            metrics = listOf(
                StartupTimingMetric(),
                FrameTimingMetric(),
                TraceSectionMetric("EnterpriseInitTraceSection")
            ),
            compilationMode = compilationMode,
            iterations = 10,
            startupMode = StartupMode.COLD,
            setupBlock = {
                // Menghapus data state sebelum COLD run jika diperlukan
                pressHome()
            }
        ) {
            startActivityAndWait()
            // Simulasikan scroll interaksi pertama
            val recycler = device.findObject(androidx.test.uiautomator.By.res("com.enterprise.app", "feed_recycler_view"))
            recycler?.let {
                it.setGestureMargin(device.displayWidth / 5)
                it.fling(androidx.test.uiautomator.Direction.DOWN)
                device.waitForIdle()
            }
        }
    }
}
```

##### File: `app/src/main/java/com/enterprise/app/profiling/AppTraceManager.kt`
```kotlin
package com.enterprise.app.profiling

import androidx.tracing.Trace

/**
 * Enterprise Tracing Abstraction untuk profiling Main Thread execution slices.
 */
object AppTraceManager {

    inline fun <T> traceSection(sectionName: String, block: () -> T): T {
        // Safe check: memotong batas string trace length agar tidak crash pada Android platform lama (maks 127 char)
        val sanitizedName = if (sectionName.length > 120) sectionName.take(120) else sectionName
        Trace.beginSection(sanitizedName)
        return try {
            block()
        } finally {
            Trace.endSection()
        }
    }
}
```

##### File: `app/src/androidTest/java/com/enterprise/app/memory/HeadlessMemoryLeakTest.kt`
```kotlin
package com.enterprise.app.memory

import android.os.Debug
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.enterprise.app.ui.CheckoutActivity
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import shark.FilteringLeakingObjectFinder
import shark.HprofHeapGraph
import shark.HprofRecord
import shark.SharkLog
import java.io.File

@RunWith(AndroidJUnit4::class)
class HeadlessMemoryLeakTest {

    @get:Rule
    val activityRule = ActivityScenarioRule(CheckoutActivity::class.java)

    @Test
    fun verifyCheckoutActivityDoesNotLeakOnFinish() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        
        // Simulasikan siklus buka-tutup Activity secara ekstrem
        activityRule.scenario.recreate()
        activityRule.scenario.close()

        instrumentation.waitForIdleSync()
        Runtime.getRuntime().gc()
        Runtime.getRuntime().runFinalization()

        // Dump heap ke file privat cache
        val hprofFile = File(context.cacheDir, "test_leak_checkout.hprof")
        if (hprofFile.exists()) hprofFile.delete()

        Debug.dumpHprofData(hprofFile.absolutePath)

        // Analisis HPROF menggunakan Engine Shark Core (komponen independen LeakCanary)
        HprofHeapGraph.open(hprofFile).use { graph ->
            val leakingInstances = graph.instances
                .filter { instance ->
                    instance.instanceClassName == CheckoutActivity::class.java.name
                }
                .toList()

            if (leakingInstances.isNotEmpty()) {
                fail("Ditemukan kebocoran memori: ${leakingInstances.size} instance dari CheckoutActivity tertahan di heap!")
            }
        }

        // Cleanup
        if (hprofFile.exists()) {
            hprofFile.delete()
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah aplikasi *Enterprise E-Commerce SuperApp* (10M+ DAU) melaporkan penurunan drastis tingkat konversi checkout dan lonjakan crash rate di platform Android:
- **Crash Rate**: Metrik Crash-Free Users turun menjadi **97.8%** akibat ledakan OOM (`OutOfMemoryError`) di perangkat segmen memori menengah-rendah (RAM 2GB–3GB, Android 10-12).
- **ANR Rate**: Tembus **0.62%** (melebihi ambang batas *Google Play Bad Behavior Threshold* 0.47%).
- **Cold Start Time**: Rata-rata P95 mencapai **3.800 ms**.
- **Jank Rate**: 18.4% frame dropped pada halaman navigasi katalog (PDP - *Product Detail Page*).

#### Metodologi Analisis Menggunakan Perfetto & Hprof Dominator Tree
1. **Perfetto SQL Trace**: Analisis file trace rekaman scroll PDP mengindikasikan Main Thread terkunci (*Blocked*) selama rata-rata 35ms per VSYNC. Eksekusi query SQLite menunjukkan adanya contention:
   ```sql
   SELECT slice.name, slice.dur/1e6 as dur_ms 
   FROM slice 
   WHERE slice.name LIKE '%inflate%' OR slice.name LIKE '%db_query%' 
   ORDER BY slice.dur DESC LIMIT 10;
   ```
   Ditemukan adanya pembacaan database Room langsung pada Main Thread di dalam ViewHolder `onBindViewHolder()` melalui referensi data class getter dinamis.
2. **Dominator Tree Analysis via MAT (Memory Analyzer Tool)**: Snapshot heap membuktikan instance `PDPActivity` tertahan sebanyak 14 instance berturut-turut pada heap space.
   - GC Root penahan: `GlobalCartBroadcastReceiver` yang didaftarkan ke ApplicationContext tanpa pernah memanggil `unregisterReceiver()`.
   - Objek terdampak: Masing-masing `PDPActivity` mengikat referensi ke Glide `Bitmap` cache lokal berukuran rata-rata ~14.2 MB (Format `Bitmap.Config.ARGB_8888`). Total retained size tembus > 200 MB, langsung menghabiskan dalvik max-heap limit (256MB).

#### Arsitektur Solusi & Resolusi
1. **Eliminasi Memory Leak**: Mengganti dynamic BroadcastReceiver dengan lifecycle-aware SharedFlow terikat di Application Scope, ditransformasikan secara aman via `Flow.flowWithLifecycle(lifecycle, Lifecycle.State.STARTED)` pada view level.
2. **Migrasi Alokasi Hardware Graphic**: Migrasi alokasi decoding bitmap ke format `Bitmap.Config.HARDWARE` (GraphicBuffer dipertahankan di memori grafis driver, memangkas dalvik heap footprint hingga 75%).
3. **Penyusunan Baseline Profiles**: Mengompilasi seluruh critical path kelas checkout dan PDP menggunakan plugin Jetpack Baseline Profile.

#### Hasil Pasca-Implementasi
- **Crash-Free Users**: Naik stabil ke **99.92%**.
- **ANR Rate**: Turun drastis menjadi **0.08%**.
- **P95 Cold Start**: Berkurang dari **3.800 ms** menjadi **1.150 ms** (pengurangan 69.7%).
- **Jank Rate (PDP Scroll)**: Turun dari 18.4% menjadi **2.1%**.

---

### 9. Trade-offs

Setiap intervensi optimasi performa memiliki konsekuensi trade-off arsitektural yang wajib diperhitungkan:

| Parameter Rekayasa | Opsi Implementasi A | Opsi Implementasi B | Analisis Trade-off Arsitektur |
| :--- | :--- | :--- | :--- |
| **Decoding Bitmap Memory** | `Bitmap.Config.ARGB_8888` (Default) | `Bitmap.Config.HARDWARE` | `HARDWARE` menyimpan memori langsung di VRAM GPU (hemat dalvik heap, mencegah OOM). Namun, bitmap bersifat *immutable* dan tidak dapat dimanipulasi secara langsung via CPU Kanvas atau pixel-level algorithms tanpa menyalin kembali ke heap. |
| **Aplikasi Profiling CI** | Baseline Profiles Otomatis | Strict JIT (Just-In-Time) Runtime | Baseline profile memperbesar ukuran download APK/AAB di Play Store sebesar 200KB - 1.5MB karena payload binary mapping profile, namun memangkas waktu eksekusi first-launch secara instan. |
| **Leak Detection Lifecycle** | Shark Core Engine di Release/Staging | LeakCanary UI hanya di Debug | Menjalankan headless Shark parsing di internal automated-QA tests mendeteksi 100% bug sebelum rilis, tetapi proses dumping `.hprof` membekukan proses aplikasi selama 2-5 detik pada saat snapshot diekstraksi. |
| **View Architecture** | Deeply Nested Layouts (Flexbox/Constraint) | Flat Layouts via Custom Layout Groups | Nested layouts memicu komputasi layout pass berganda ($O(2^n)$ pada Nested RelativeLayouts). Flat layouts menghemat waktu eksekusi CPU, tetapi meningkatkan kompleksitas maintenance kode XML/Compose. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Mengabaikan Penahanan Context pada View/Adapter di Background Thread
- **Gejala**: OutOfMemoryError acak yang terjadi beberapa menit setelah user berpindah-pindah activity.
- **Penyebab**: Menyimpan instance `Context` (terutama Activity Context) di dalam constructor class non-lifecycle, seperti Singleton, Static List, atau ImageLoader callback lambda.
- **Solusi**: Gunakan `ApplicationContext` untuk lifecycle agnostik, atau ubah referensi menjadi `WeakReference<Context>`.

#### Kesalahan 2: Overdraw & Frame Stall akibat Alokasi Objek di Jalur Gambar (Draw Path)
- **Gejala**: SysTrace menunjukkan eksekusi `onDraw()` memakan waktu > 5ms secara berulang; GC terpicu sangat sering (Logcat ART GC: `Explicit concurrent mark sweep`).
- **Penyebab**: Instansiasi objek baru (seperti `val paint = Paint()`, `val path = Path()`, atau alokasi string formatting) di dalam loop method `onDraw()`.
- **Solusi**: Inisialisasi seluruh variabel gambar di level class constructor/init, gunakan primitive type pool, hindari alokasi memory apapun saat proses rendering VSYNC berjalan.

#### Kesalahan 3: Baseline Profiles Tidak Efektif / Hilang di Production Bundle
- **Gejala**: Benchmark lokal menunjukkan peningkatan performa, tetapi angka Play Console Vitals untuk Cold Start tetap lambat.
- **Penyebab**: Build release tidak ditandatangani dengan benar, atau task Gradle `generateBaselineProfile` dieksekusi tanpa menerapkan `applyProfile = true`, atau package mapping mengalami *obfuscation mismatch* akibat aturan Proguard/R8 yang tidak sinkron dengan rules profile.
- **Solusi**: Lakukan dekompilasi AAB rilis dan pastikan direktori `assets/dexopt/baseline.prof` tersedia di dalam binary release.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebagai *Quality Gate* sebelum mempromosikan build ke production:

```markdown
[ ] Memory Profiling:
    [ ] Tidak ada Activity / Fragment tertahan setelah onDestroy() (diverifikasi via Shark dump).
    [ ] Uncompressed Bitmaps di-scale sesuai display pixel density (inSampleSize / target layout bounds).
    [ ] Seluruh BroadcastReceiver, EventBus, SensorEventListener dipastikan unregister di onStop() / onDestroy().
    [ ] Image loader diatur agar menggunakan format Bitmap.Config.HARDWARE untuk read-only visual assets.

[ ] Rendering & Jank Prevention:
    [ ] Tidak ada eksekusi I/O (Disk, Database Room, SharedPrefs, IPC) di Main Thread.
    [ ] Hierarki UI memiliki kedalaman nesting < 8 level; rasio Overdraw pada GPU Debugging <= 2x (Hijau/Biru muda).
    [ ] P99 Frame Time di bawah 16.6ms (layar 60Hz) atau 8.3ms (layar 120Hz) pada perangkat target acuan minimal.

[ ] Benchmarking & Startup:
    [ ] Baseline Profiles di-generate menggunakan skenario interaksi UI kritis nyata.
    [ ] Metrik TTID (Time To Initial Display) < 800ms dan TTFD (Time To Full Display) < 1500ms pada Cold Start.
    [ ] Macrobenchmark regression tests terintegrasi di CI/CD dengan threshold alert yang aktif.
```

---

### 12. Hands-on Practice

Buat dan simpan latihan ini pada direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Modul Macrobenchmark
Buka project enterprise Anda via terminal, buat direktori benchmark baru jika belum ada:
```bash
mkdir -p hands-on/m02/benchmark
```

#### Langkah 2: Tambahkan Skrip Gradle untuk Engine Benchmark
Buat file `hands-on/m02/benchmark/build.gradle.kts`:
```kotlin
plugins {
    id("com.android.test")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.enterprise.quality.benchmark"
    compileSdk = 34

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    defaultConfig {
        minSdk = 28
        targetSdk = 34
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    targetProjectPath = ":app"
    experimentalProperties["android.experimental.self-instrumenting"] = true
}

dependencies {
    implementation("androidx.test.ext:junit:1.1.5")
    implementation("androidx.test.uiautomator:uiautomator:2.3.0")
    implementation("androidx.benchmark:benchmark-macro-junit4:1.2.3")
}
```

#### Langkah 3: Implementasi Baseline Profile Generator Test
Buat file `hands-on/m02/benchmark/src/main/java/com/enterprise/quality/benchmark/BaselineProfileGenerator.kt`:
```kotlin
package com.enterprise.quality.benchmark

import androidx.benchmark.macro.junit4.BaselineProfileRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class BaselineProfileGenerator {

    @get:Rule
    val baselineProfileRule = BaselineProfileRule()

    @Test
    fun generateAppBaselineProfiles() {
        baselineProfileRule.collect(
            packageName = "com.enterprise.app",
            includeInStartupProfile = true
        ) {
            // Startup Journey
            pressHome()
            startActivityAndWait()

            // Lakukan simulasi navigasi utama pengguna
            val feedList = device.findObject(androidx.test.uiautomator.By.res("com.enterprise.app", "recycler_catalog"))
            if (feedList != null) {
                feedList.fling(androidx.test.uiautomator.Direction.DOWN)
                device.waitForIdle()
                feedList.fling(androidx.test.uiautomator.Direction.UP)
            }
        }
    }
}
```

#### Langkah 4: Eksekusi Profiler via CLI & Capture Perfetto Trace
Jalankan perintah ADB berikut untuk menghasilkan profile trace mentah dan mengubahnya menjadi format Perfetto yang dapat dianalisis:
```bash
# Set device properties untuk mengizinkan tracing Macrobenchmark
adb shell setprop debug.renderengine.backend skiagl
adb shell setprop security.perf_harden 0

# Eksekusi benchmark profile generation
./gradlew :benchmark:connectedCheck -Pandroid.testInstrumentationRunnerArguments.class=com.enterprise.quality.benchmark.BaselineProfileGenerator

# Tangkap traces Perfetto langsung dari shell Android untuk sesi interaksi UI 5 detik
adb shell perfetto \
  -c - --txt \
  -o /data/misc/perfetto-traces/trace.perfetto-trace <<EOF
buffers: {
    size_kb: 65536
    fill_policy: RING_BUFFER
}
data_sources: {
    config {
        name: "linux.ftrace"
        ftrace_config {
            ftrace_events: "sched_switch"
            ftrace_events: "power/cpu_frequency"
            atrace_categories: "view"
            atrace_categories: "app"
            atrace_categories: "am"
            atrace_apps: "com.enterprise.app"
        }
    }
}
duration_ms: 5000
EOF

# Tarik trace keluar dari emulator/perangkat
adb pull /data/misc/perfetto-traces/trace.perfetto-trace ./hands-on/m02/trace.perfetto-trace
```
Buka file `trace.perfetto-trace` pada peramban web di `ui.perfetto.dev` untuk menganalisis waktu frame traversal dan alokasi slice runtime.

---

### 13. Exercise

#### Level Easy
Terdapat sebuah custom `View` yang menggambar penunjuk loading manual:
```kotlin
class LoadingSpinnerView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val paint = Paint().apply {
            color = Color.RED
            strokeWidth = 8f
            style = Paint.Style.STROKE
        }
        canvas.drawCircle(width / 2f, height / 2f, 40f, paint)
        invalidate() // Loop redraw tak terbatas
    }
}
```
**Tugas**: Perbaiki class di atas agar tidak memicu alokasi memori berulang pada heap saat `onDraw()` dan hilangkan pemanggilan redraw tak terkontrol yang memicu 100% CPU core utilization.

#### Level Medium
Sebuah modul `LocationTracker` didesain sebagai arsitektur Singleton. Modul ini meminta listener:
```kotlin
object LocationTracker {
    private val listeners = mutableListOf<(Location) -> Unit>()
    fun addListener(listener: (Location) -> Unit) { listeners.add(listener) }
    fun onLocationChanged(loc: Location) { listeners.forEach { it(loc) } }
}
```
Di dalam sebuah Fragment:
```kotlin
class MapFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        LocationTracker.addListener { newLoc ->
            view.findViewById<TextView>(R.id.coords).text = "${newLoc.latitude}"
        }
    }
}
```
**Tugas**: Tuliskan ulang `LocationTracker` dan `MapFragment` menggunakan kombinasi `LifecycleObserver` atau `StateFlow` agar `MapFragment` dan `View`-nya bebas dari kebocoran memori saat Fragment diganti (*swapped*) dalam `FragmentTransaction`.

#### Level Hard
Sebuah fungsi memproses decoding array byte gambar resolusi ultra-tinggi (8K) yang dikirim oleh modul kamera eksternal dan menampilkannya pada UI thread:
```kotlin
fun renderRawPayload(payload: ByteArray, targetView: ImageView) {
    val bitmap = BitmapFactory.decodeByteArray(payload, 0, payload.size)
    targetView.setImageBitmap(bitmap)
}
```
Ketika dijalankan pada perangkat dengan batas heap 192MB, fungsi ini langsung menghasilkan `java.lang.OutOfMemoryError: Failed to allocate a ... byte allocation with ... free bytes and ... until OOM`.

**Tugas**: Buat arsitektur pipeline decoding yang aman secara komprehensif menggunakan:
1. `BitmapFactory.Options` dengan perhitungan rasio `inSampleSize` dinamis sesuai resolusi layar perangkat.
2. Penggunaan reuse pool via `inBitmap` untuk menghindari realokasi memori heap.
3. Thread offloading ke `Dispatchers.Default` dengan validasi parsing lifecycle agar `ImageView` hanya di-update jika konteks pemanggil masih dalam status *Alive*.

---

### 14. Challenge

#### Skenario Studi Kasus Sistem Finansial (High-Frequency Trading Dashboard)
Perusahaan Anda meluncurkan aplikasi *mobile trading workstation*. Aplikasi menerima data streaming order book via WebSocket berkecepatan tinggi (~150 update per detik) yang memuat ribuan baris fluktuasi harga per detik.

**Masalah Kritis**:
1. Aplikasi mengalami *freezing* mikro (*micro-stuttering*) berulang kali: ART Generational CC GC terpicu setiap 1.5 detik, membekukan animasi ticker chart.
2. Saat aplikasi dipindahkan ke mode background lalu kembali ke foreground setelah 15 menit, konsumsi memory melonjak drastis hingga sistem Linux kernel mengeksekusi `lmkd` via sinyal `SIGKILL` (proses hilang tanpa log crash).
3. Frame rendering rate anjlok dari 120 FPS ke 32 FPS pada layar Samsung/Pixel bertipe refresh rate adaptif.

**Instruksi Misi Rekayasa**:
1. Rancang arsitektur data pipeline dari layer Network WebSocket hingga UI Layer tanpa memicu *object allocation thrashing* pada heap. Tentukan struktur buffer data yang akan digunakan (misalnya *Circular Primitive Buffers*, *Array Pooling*, atau *Object Recycling*).
2. Susun sistem throttling/conflation adaptif yang menyelaraskan frekuensi pembaruan UI dengan siklus sinyal VSYNC yang dilaporkan oleh `Choreographer.FrameCallback`.
3. Buat rencana pengujian regresi headless berbasis Macrobenchmark dan instrumen Perfetto SQL script untuk membuktikan bahwa throughput 150 event/detik menghasilkan zero-drop frames pada batas 120 FPS tanpa alokasi baru di dalam draw phase.

*Catatan: Tidak disediakan template jawaban untuk challenge ini. Rancang dan uji solusi arsitektural Anda secara mandiri.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (Pilihan Ganda)

1. Apa fungsi utama dari hardware read barrier pada algoritma ART Concurrent Copying (CC) Garbage Collector?
   - A. Mencegah thread selain GC menulis ke variabel primitif.
   - B. Memastikan thread aplikasi menerima alamat memori terbaru dari objek yang dipindahkan (*to-space*) saat fase compaction berlangsung tanpa full-stop.
   - C. Mengenkripsi alokasi memori di heap agar tidak dapat dibaca oleh proses root lain.
   - D. Menghubungkan proses compiler Just-In-Time (JIT) ke direktori Dalvik Cache.

2. Komponen sistem operasi Linux Android manakah yang bertanggung jawab mengeksekusi sinyal `SIGKILL` pada proses aplikasi saat perangkat mengalami defisit memori ekstrem?
   - A. Zygote Init Process.
   - B. SurfaceFlinger Engine.
   - C. Low Memory Killer Daemon (`lmkd`).
   - D. ART Heap Verifier.

3. Apa efek samping utama dari kebocoran memori (*memory leak*) bertipe penahanan referensi `Activity` oleh class Singleton?
   - A. Aplikasi seketika mengalami crash dengan tipe `NullPointerException`.
   - B. Objek Activity beserta seluruh hierarki View dan Bitmap di dalamnya tertahan di heap, memicu pemborosan RAM dan eventual `OutOfMemoryError`.
   - C. Versi OS Android akan otomatis mendowngrade aplikasi ke mode kompatibilitas render 30Hz.
   - D. Dalvik Executable (DEX) akan membatalkan bytecode kompilasi AOT.

4. Pada siklus rendering Android, callback `Choreographer` dijalankan dalam urutan apa?
   - A. DRAW -> LAYOUT -> INPUT.
   - B. ANIMATION -> TRAVERSAL -> COMMIT.
   - C. INPUT -> ANIMATION -> TRAVERSAL.
   - D. MEASURE -> LAYOUT -> INPUT.

5. File biner Baseline Profiles (`baseline.prof`) pada Android App Bundle berfungsi untuk:
   - A. Mengompres file layout XML menjadi flat binary formats.
   - B. Memberikan petunjuk jalur kode kritis (*critical paths*) kepada sistem instalasi (ART dex2oat) untuk dikompilasi ke format *machine code* secara Ahead-Of-Time (AOT).
   - C. Menghapus class library pihak ketiga yang tidak terpanggil pada bytecode release.
   - D. Menyamarkan (*obfuscate*) nama variabel untuk mencegah pembajakan reverse engineering.

---

#### Bagian B: Intermediate (Pilihan Ganda Tingkat Lanjut)

6. Mengapa metrik `PSS` (Proportional Set Size) dianggap jauh lebih representatif dibanding `RSS` (Resident Set Size) saat menganalisis konsumsi memori aplikasi Android?
   - A. PSS mencakup alokasi register CPU core secara langsung.
   - B. PSS membagi proporsi memori library bersama (*shared memory pages*) dengan jumlah proses lain yang menggunakan library yang sama, sehingga tidak terjadi penghitungan ganda.
   - C. PSS hanya mengukur alokasi memori yang dilakukan pada heap C/C++ native runtime.
   - D. RSS tidak dapat dihitung oleh command line `dumpsys meminfo`.

7. Perhatikan potongan kode berikut:
   ```kotlin
   class MetricCollector private constructor(val ctx: Context) {
       companion object {
           @Volatile private var INSTANCE: MetricCollector? = null
           fun init(ctx: Context) = INSTANCE ?: synchronized(this) {
               INSTANCE ?: MetricCollector(ctx).also { INSTANCE = it }
           }
       }
   }
   ```
   Jika `MetricCollector.init(this)` dipanggil dari dalam `MainActivity.onCreate()`, potensi risiko terburuknya adalah:
   - A. Deadlock pada block synchronized.
   - B. `MainActivity` tidak dapat direklamasi oleh GC selamanya karena tertahan oleh singleton instance, menyebabkan kebocoran memori skala penuh.
   - C. Terjadi exception `ClassCastException` saat runtime.
   - D. GC akan langsung mematikan aplikasi saat fragment navigation.

8. Manakah konfigurasi Bitmap berikut yang **TIDAK** menggunakan dalvik memory heap dan mengalokasikan data piksel langsung ke Graphic Buffer perangkat keras GPU?
   - A. `Bitmap.Config.ALPHA_8`
   - B. `Bitmap.Config.RGB_565`
   - C. `Bitmap.Config.ARGB_8888`
   - D. `Bitmap.Config.HARDWARE`

9. Dalam pengujian Jetpack Macrobenchmark, apa perbedaan fundamental antara `CompilationMode.None()` dan `CompilationMode.Partial(BaselineProfileMode.Require)`?
   - A. `None()` memaksa aplikasi diuji tanpa izin internet, sedangkan `Partial()` memberikan akses mock network.
   - B. `None()` merepresentasikan skenario aplikasi berjalan murni di bawah interpretasi/JIT tanpa optimasi profil, sedangkan `Partial()` menguji performa ketika aplikasi telah dioptimasi oleh *Baseline Profile*.
   - C. `None()` menonaktifkan pengujian garbage collector saat benchmarking.
   - D. `Partial()` mematikan eksekusi RenderThread secara sementara.

10. Ketika menganalisis file Perfetto trace, Anda melihat slice thread utama terhenti (*State: S - Sleeping / Uninterruptible Sleep*) dengan label eksekusi mutex wait pada `openDexFile` atau `mmap`. Hal ini umumnya menandakan terjadinya:
    - A. GPU Overdraw tingkat tinggi pada view layer.
    - B. Disk I/O contention atau pemuatan class dinamis (*class loading latency*) yang mengunci Main Thread saat JIT kompilasi berlangsung.
    - C. Baterai perangkat berada pada status Battery Saver Mode.
    - D. Logcat buffer sistem sedang mengalami overflow.

---

#### Bagian C: Skenario Kasus Produksi

11. **Skenario 1**: Tim Anda merilis fitur video feed baru. Di Google Play Vitals, metrik **Slow Frames (Frames > 50ms)** melonjak dari 1.2% menjadi 9.8%. Saat dilakukan trace Perfetto, ditemukan slice `Choreographer#doFrame` sering memakan waktu 45-60ms dengan trace child `View.draw()` yang memanggil instansiasi parsing format teks dan custom shape paint object berulang kali di dalam custom view adapter.
    - **Pertanyaan**: Apa langkah arsitektural yang paling efektif untuk mengembalikan metrik slow frame tersebut ke bawah standar 1.5% tanpa menghapus fitur visual yang bersangkutan?
    - A. Pindahkan eksekusi parsing teks dan alokasi konfigurasi Paint ke level Presenter/State Layer (`ViewModel` atau Model mapping phase) serta caching static properties di constructor Custom View; hapus alokasi dinamis di dalam `onDraw()`.
    - B. Ubah resolusi perangkat secara paksa menggunakan perintah `wm density` via runtime reflection.
    - C. Pasang flag `android:hardwareAccelerated="false"` pada file `AndroidManifest.xml` untuk membebaskan RenderThread.
    - D. Jalankan pemanggilan `Runtime.getRuntime().gc()` secara manual setiap kali user selesai melakukan scroll video feed.

12. **Skenario 2**: Aplikasi institusi perbankan yang memiliki proteksi keamanan tinggi mendeteksi bahwa integrasi Shark / LeakCanary pada debug build menyebabkan automated testing suite di Firebase Test Lab sering *timed out* (melebihi batas eksekusi maksimum 45 menit). Investigasi menunjukkan analisis dumping memori heap memakan waktu rata-rata 35 detik per skenario test.
    - **Pertanyaan**: Bagaimana Anda mengoptimalkan strategi testing assertion kebocoran memori ini agar pipeline automated QA selesai tepat waktu namun tetap menjamin bebas kebocoran memori pada class kritis?
    - A. Matikan deteksi memori sepenuhnya dan andalkan laporan bug manual dari tim audit internal.
    - B. Batasi dumping memori hanya pada end-of-test session untuk subset *Critical User Journeys* (misal: Transaksi & Otentikasi) dan filter pencarian HPROF graph khusus untuk turunan instance class target tertentu (`Activity`, `Fragment`, `ViewModel`) menggunakan class-name string matching, alih-alih melakukan full-heap reference tree traversals pada setiap interaksi.
    - C. Tingkatkan timeout Firebase Test Lab menjadi 120 menit tanpa mengubah arsitektur test.
    - D. Lakukan dekompilasi APK sebelum dikirim ke Test Lab untuk menghapus seluruh class Shark.

13. **Skenario 3**: Sebuah super-app mengalami fenomena di mana pengguna dengan handphone low-end mengeluh bahwa setiap kali mereka memotret dokumen identitas (KTP) melalui kamera custom, aplikasi tiba-tiba menutup sendiri dan kembali ke layar beranda OS (*Home Screen*) tanpa ada dialog "App Has Stopped" dan tanpa adanya crash trace yang terekam di Crashlytics.
    - **Pertanyaan**: Berdasarkan internal arsitektur Linux dan ART, apa analisis teknis yang tepat terhadap fenomena ini, dan bagaimana solusi arsitekturalnya?
    - A. Aplikasi mengalami `StackOverflowError` yang langsung diabaikan oleh logger Crashlytics; solusinya adalah menaikkan ukuran stack thread.
    - B. Pembacaan kamera memicu alokasi byte array gambar mentah uncompressed yang sangat masif di memory, menyebabkan RAM fisik habis secara mendadak sehingga kernel Linux `lmkd` membunuh proses via sinyal `SIGKILL` (yang membypass Crashlytics exception handler); solusinya adalah streaming byte stream ke file storage atau menggunakan `ImageReader` dengan format YUV/HardwareBuffer dan downsampling sebelum decoding.
    - C. Driver hardware kamera merestart runtime Android (SurfaceFlinger crash); solusinya adalah meminta pengguna merestart perangkat.
    - D. Nilai `oom_score_adj` aplikasi diubah oleh OS menjadi `-1000` secara sengaja; solusinya adalah menyalakan service bertipe Foreground Service dengan notifikasi aktif.

---

#### Kunci Jawaban & Rasionalisasi Mendalam

1. **B**: *Read barrier* bertugas secara atomik membelokkan akses baca pointer ke alamat *to-space* saat sebuah objek dipindahkan selama proses pemadatan memori heap (*compaction*) berlangsung tanpa mematikan thread aplikasi secara total.
2. **C**: `lmkd` (Low Memory Killer Daemon) adalah service user-space yang bertugas memantau tekanan kernel memory dan mengirim sinyal `SIGKILL` secara sepihak ke proses ber-`oom_score_adj` paling tinggi saat batas *watermark* terlewati.
3. **B**: Activity mengikat referensi ke seluruh pohon hierarki layout UI, Drawable, dan resource Context. Kebocoran satu Activity menahan puluhan megabyte data di heap, mengikis sisa kuota heap dan berujung fatal pada OOM.
4. **C**: Choreographer memproses pesan VSYNC secara deterministik dalam urutan: Input Events (sentuhan layar), Animations (interpolator value), dan Traversals (Measure, Layout, Draw pipeline).
5. **B**: Baseline Profile menyediakan metadata panduan kompilasi Ahead-Of-Time (AOT) untuk ART compiler `dex2oat` di perangkat target, mengompilasi class dan method kritis ke format native machine code sebelum aplikasi pertama kali dieksekusi oleh pengguna.
6. **B**: RSS mencakup seluruh pemetaan library fisik bersama, sehingga jika 10 proses memakai `libc.so`, ukurannya dihitung 10 kali secara terpisah. PSS membagi ukuran halaman memori shared tersebut secara adil di antara semua proses yang menggunakannya, menjadikannya metrik paling akurat untuk mengukur pemakaian memori riil.
7. **B**: Menyimpan `Context` level Activity ke dalam objek singleton statis yang hidup sepanjang lifecycle proses aplikasi adalah akar kebocoran memori klasik terparah di ekosistem Android. Instance Activity tidak akan pernah bisa di-garbage collect.
8. **D**: Konfigurasi `Bitmap.Config.HARDWARE` memetakan graphic buffer langsung ke memori yang diakses oleh hardware GPU, melewati dalvik heap sepenuhnya dan mencegah fragmentasi heap.
9. **B**: Mode `CompilationMode.None` menyimulasikan pengalaman aplikasi mentah tanpa optimasi AOT (bergantung pada JIT interpreter lambat), sedangkan `Partial` menguji efisiensi eksekusi saat biner telah dioptimasi oleh *Baseline Profile*.
10. **B**: State *Uninterruptible Sleep* dengan trace I/O atau lock loading class menandakan thread utama terhenti menunggu pembacaan disk storage yang lambat, fenomena umum saat kompilasi JIT terpaksa membaca instruksi DEX langsung dari storage di tengah interaksi pengguna.
11. **A**: Mengalokasikan objek baru di dalam metode `onDraw()` dan mengeksekusi text parsing adalah anti-pattern fatal pada pipeline HWUI. Memindahkan komputasi dan alokasi ke state initialization layer memastikan waktu eksekusi rendering kembali berada di bawah ambang batas 16.6ms/8.3ms per frame.
12. **B**: Dumping dan penguraian file `.hprof` adalah operasi I/O dan komputasi intensif. Menargetkan assertion hanya pada alur transaksi inti dan membatasi traversal heap graph untuk class penampung besar secara dramatis mempercepat pengujian tanpa mengorbankan kualitas rilis.
13. **B**: Ketiadaan laporan di Firebase Crashlytics adalah tanda khas dari intervensi kernel Linux `SIGKILL` via `lmkd`. Alokasi array citra berukuran masif melampaui kapasitas RAM perangkat low-end dan langsung memicu pembersihan paksa oleh sistem operasi tanpa memicu uncaught exception handler pada level JVM.

---

### 16. Summary

- **ART Memory Optimization**: Manajemen memori pada Android modern dikendalikan oleh ART Generational Concurrent Copying GC. Pemahaman terhadap pemisahan ruang alokasi (*Young Gen*, *Old Gen*, *LOS*) dan interaksi kernel Linux melalui `lmkd` sangat fundamental untuk mencegah terminasi paksa proses (`SIGKILL`).
- **Memory Leak Mitigation**: Kebocoran memori pada platform Android umumnya bersumber dari penahanan referensi lifecycle pendek (`Activity`, `Fragment`, `View`) oleh objek lifecycle panjang (`Singleton`, `Coroutines Job`, `Static Listener`). Integrasi Shark/LeakCanary di staging dan headless test memungkinkan deteksi regresi secara proaktif sebelum rilis ke production.
- **Rendering Performance**: Untuk mempertahankan kelancaran UI pada 60 FPS atau 120 FPS, total waktu eksekusi di Main Thread dan RenderThread tidak boleh melampaui interval VSYNC yang diorkestrasikan oleh `Choreographer`. Alokasi objek di dalam `onDraw()` serta eksekusi I/O di Main Thread adalah pemicu utama *Jank*.
- **Benchmarking & Profiles**: Mengukur performa secara empiris menuntut standardisasi metrik berbasis P95/P99. Implementasi **Jetpack Macrobenchmark** yang dikombinasikan dengan **Baseline Profiles** secara terbukti memangkas latensi Cold Start dan mengeliminasi overhead kompilasi JIT runtime pada critical user journeys.