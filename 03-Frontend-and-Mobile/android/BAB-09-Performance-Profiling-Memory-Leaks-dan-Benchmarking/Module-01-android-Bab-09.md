# BAB 09 MODULE 01: Performance Profiling, Memory Leaks, & Benchmarking

---

## SEKSI 01 — IDENTITAS MODUL

* **Track:** Android Enterprise Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Topik:** Performance Profiling, Memory Leaks, & Benchmarking
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Teknis:** 
  * Pemahaman mendalam tentang siklus hidup Android Framework (Activity, Fragment, View, Service).
  * Penguasaan Kotlin Memory Model, Concurrency (Coroutines, Flow), dan Java Virtual Machine (JVM/ART) Architecture.
  * Familiaritas dengan Android Studio Profiler, Gradle build systems, dan Jetpack Compose rendering internals.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Membedah ART Runtime:** Memahami alokasi memori internal Android Runtime (ART), Garbage Collection (Generational CMC & Concurrent Mark-Sweep), serta siklus heap allocation.
2. **Mendeteksi dan Memitigasi Memory Leaks Kompleks:** Mengidentifikasi kebocoran memori berbasis *retained references* menggunakan Android Studio Profiler, `adb shell dumpsys meminfo`, serta integrasi otomatis via LeakCanary.
3. **Melakukan Systrace & Perfetto Deep Profiling:** Menangkap trace visual, membaca frame rendering pipeline (Choreographer, SurfaceFlinger), dan mengidentifikasi penyebab jank (UI thread preemption).
4. **Mengimplementasikan Automated Benchmarking:** Membangun test suite performa menggunakan Jetpack Macrobenchmark dan Microbenchmark API dengan metrik startup time, frame timing, dan scroll performance.
5. **Mengisolasi Overhead Rendering Jetpack Compose:** Mengaudit recomposition loop yang tidak perlu melalui Compose Compiler Metrics dan Layout Inspector.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Mental Model: Dari "Feature-First" ke "Resource-Conscious"
Mayoritas engineer mengasumsikan perangkat keras modern memiliki sumber daya tak terbatas. Di Android, eksekusi kode berjalan di bawah batasan agresif sistem operasi: Linux Low Memory Killer (LMK), thermal throttling hardware, dan ART Garbage Collector yang dapat membekukan eksekusi thread.

```
       TRADISIONAL                        ENTERPRISE PERFORMANCE-DRIVEN
┌─────────────────────────┐            ┌───────────────────────────────────┐
│     Tulis Kode          │            │  Desain berdasarkan Budget Memory │
│         │               │            │           │                       │
│         ▼               │            │           ▼                       │
│    Uji Fungsional       │            │  Ukur Alokasi & Frame Budget      │
│         │               │            │  (16.6ms @60Hz, 8.3ms @120Hz)     │
│         ▼               │            │           │                       │
│ Release ke Production   │            │           ▼                       │
│         │               │            │  Audit GC Triggers & Tracing      │
│         ▼               │            │           │                       │
│ Reaktif terhadap Crash  │            │           ▼                       │
│ (OOM di Firebase Crash) │            │  Automated Macrobenchmark di CI   │
└─────────────────────────┘            └───────────────────────────────────┘
```

Prinsip inti Staff Engineer:
* **Alokasi adalah Utang Performa:** Setiap objek yang dialokasikan pada UI thread pada akhirnya harus dikumpulkan oleh Garbage Collector. Hindari *churn rate* tinggi.
* **Frame Budget adalah Hukum Fisika:** Layar 60Hz memberi waktu 16.6ms per frame; layar 120Hz memberi waktu 8.3ms. Melebihi budget tersebut menyebabkan *jank* (dropped frames).
* **Profil Sebelum Mengoptimasi:** Optimasi tanpa data telemetri/trace adalah spekulasi liar. Gunakan profiler untuk menemukan *bottleneck* aktual.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Alur: Rendering Pipeline, VSYNC, dan ART GC Pause

```
[Hardware Display Controller]
       │
       │ VSYNC Pulse (tiap 8.3ms / 16.6ms)
       ▼
┌────────────────── UI THREAD (App Process) ────────────────────────┐
│                                                                   │
│  Choreographer.doFrame()                                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 1. Input Handling -> 2. Animation -> 3. Traversal (Measure, │  │
│  │    Layout, Draw) -> Compose Recomposition / Layout          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                │                                  │
│                                ▼                                  │
│                 RenderThread.syncAndDrive()                       │
└────────────────────────────────┼──────────────────────────────────┘
                                 │
                                 ▼
┌────────────────── RENDER THREAD (App Process) ────────────────────┐
│  DrawFrameTask -> Upload GPU Shaders -> EGL swapBuffers()         │
└────────────────────────────────┼──────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────── SURFACEFLINGER ─────────────────────────┐
│  Compositor menyatukan Hardware Layer -> FrameBuffer ke Panel     │
└───────────────────────────────────────────────────────────────────┘
                                 ▲
                                 │
   MASALAH: JANK TERJADI JIKA UI THREAD / RENDER THREAD TERHAMBAT
                                 │
 ┌───────────────────────────────┴─────────────────────────────────┐
 │ GC Interruption: Generational Concurrent Copying (CC) GC        │
 │ - Thread Suspended (Stop-The-World) untuk Roots Scanning         │
 │ - Excessive Object Allocation Churn pada UI Loop                │
 │ - Heavy I/O Disk Read atau Lock Contention di Main Thread       │
 └─────────────────────────────────────────────────────────────────┘
```

### Siklus Penanganan Memori: Dari Alokasi hingga LMKD Termination

```
┌──────────────────────────────────────────────────────────────────┐
│                   ANDROID RUNTIME (ART) HEAP                     │
│                                                                  │
│  ┌─────────────────────────┐      ┌───────────────────────────┐  │
│  │     Young Generation    │      │      Old Generation       │  │
│  │  (Eden + Survivor Space)│─────>│       (Tenured Space)     │  │
│  └─────────────────────────┘      └───────────────────────────┘  │
│               │                                 │                │
│               ▼                                 ▼                │
│       Concurrent Minor GC              Concurrent Mark-Sweep     │
└─────────────────────────────────────────────────┬────────────────┘
                                                  │
                                                  ▼
                                      Jika Heap Limit Terlampaui
                                                  │
                                                  ▼
┌─────────────────────────────────────────── OutOfMemoryError ─────┐
│ OS LEVEL (Linux Kernel):                                         │
│ Memori Menipis -> vmpressure event naik                         │
│ -> Low Memory Killer Daemon (lmkd) mengecek oom_score_adj        │
│ -> Kill Background Processes -> Kill Foreground Processes        │
└──────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. ART Garbage Collection: Generational Concurrent Copying (CC)
Mulai dari Android 8.0 (Oreo) dan disempurnakan pada versi Android modern, ART menggunakan algoritma **Generational Concurrent Copying**. 
* **Young Gen:** Memori dibagi menjadi region-region kecil. Objek yang baru dibuat dialokasikan di sini. Karena sebagian besar objek berumur pendek (*weak generational hypothesis*), minor collection membersihkan region ini dengan menyalin objek yang bertahan ke survivor region secara paralel dengan eksekusi aplikasi.
* **Stop-The-World (STW) Pauses:** Berbeda dengan Dalvik lama yang memblokir eksekusi lama, ART CC hanya melakukan STW pause berdurasi sub-milidetik (biasanya < 1ms) untuk sinkronisasi thread roots scanning. Namun, jika alokasi meledak dalam kecepatan tinggi (*allocation churn*), thread alokasi akan dipaksa melakukan *mutator-assisted GC*, yang memblokir UI thread secara signifikan.

### 2. Memori Komponen Android: PSS, RSS, dan VSS
* **VSS (Virtual Set Size):** Seluruh alamat virtual yang diakses proses.
* **RSS (Resident Set Size):** Memori fisik yang dialokasikan, termasuk shared libraries secara penuh.
* **PSS (Proportional Set Size):** Metrik paling akurat di Android. PSS menghitung private memory proses ditambah pembagian proporsional shared libraries dengan proses lain. LMKD menggunakan PSS untuk kalkulasi batas konsumsi sistem.

### 3. VSYNC dan Render Pipeline
UI Android digerakkan oleh denyut sinyal periodik hardware yang disebut **VSYNC**. 
* Ketika VSYNC tiba, `Choreographer` menerima interrupt dan mengeksekusi callback: Input -> Animation -> Traversal.
* Jika eksekusi kode di Main Thread memakan waktu 18ms pada layar 60Hz (batas: 16.6ms), `Choreographer` akan melewatkan VSYNC berikutnya. Frame tersebut di-drop, pengguna melihat layar terhenti sesaat (*jank*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Akar Masalah Memory Leaks: GC Root & Retained References
Secara formal, memori bocor di Android terjadi ketika suatu objek tidak lagi digunakan oleh logika bisnis aplikasi, tetapi masih dapat dijangkau (*reachable*) melalui rantai traversal referensi dari **GC Root**.

```
[GC ROOT]
(Class Static Field / Active Thread / JNI Global Ref)
      │
      ▼ Strong Reference
[CustomSingleton / Listener]
      │
      ▼ Strong Reference
[Activity Instance (sudah onDestroy())]
      │
      ▼
[DecorView -> Large Bitmap (100MB Retained)]
```

Daftar GC Roots umum di Android:
1. **Thread Aktif:** Instansiasi `Thread`, Coroutine `Job` yang tidak dibatalkan, atau Java `Executor` yang memegang referensi context.
2. **Static Variables:** Variabel `companion object` atau Java `static` yang menyimpan `Context`, `View`, atau listener.
3. **JNI Global References:** Pointer alokasi native C/C++ yang tidak di-free via `DeleteGlobalRef`.
4. **Android OS Callbacks:** SensorManager, LocationManager, atau InputMethodManager yang me-register listener tanpa di-unregister di `onDestroy()`.

### Jetpack Compose: Recomposition & Allocation Trap
Jetpack Compose tidak menggunakan View Hierarchy hierarkis konvensional (`View` tree), melainkan struktur *Slot Table*. Permasalahan performa di Compose umumnya bukan kebocoran memori View klasik, melainkan:
* **Unstable Parameter Triggers:** Parameter lambda yang meng-capture instansiasi objek dinamis atau data class yang tidak di-annotate `@Immutable` / `@Stable` menyebabkan fungsi Composable kehilangan kemampuan *skipping*.
* **Allocation inside `@Composable` Scope:** Instansiasi objek (misalnya `SimpleDateFormat`, alokasi List baru, penataan regex) langsung di dalam body Composable tanpa `remember` akan dieksekusi setiap recomposition loop, menyebabkan lonjakan alokasi (*allocation churn*) yang memicu minor GC beruntun.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan kode anti-pattern memory leak klasik versus mitigasi arsitektur modern menggunakan Coroutine lifecycle-aware, weak referencing, dan proper clean up.

### Kode Bermasalah: Anti-Pattern Leak

```kotlin
// MemoryLeakTargetActivity.kt (ANTI-PATTERN)
package com.enterprise.performance.fundamental

import android.app.Activity
import android.graphics.Bitmap
import android.os.Bundle

object SensorEventHub {
    // GC ROOT: Static collections menyimpan referensi selamanya
    private val listeners = mutableListOf<OnSensorChangedListener>()

    fun register(listener: OnSensorChangedListener) {
        listeners.add(listener)
    }

    fun unregister(listener: OnSensorChangedListener) {
        listeners.remove(listener)
    }
}

interface OnSensorChangedListener {
    fun onData(value: FloatArray)
}

class LeakingActivity : Activity(), OnSensorChangedListener {
    // Alokasi memori masif
    private val heavyBuffer = ByteArray(1024 * 1024 * 32) // 32MB buffer

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // BUG: Mendaftarkan 'this' ke Singleton tanpa unregister di onDestroy()
        SensorEventHub.register(this)
    }

    override fun onData(value: FloatArray) {
        // Handle sensor data
    }
    // onDestroy() tidak memanggil SensorEventHub.unregister(this)
    // HASIL: Seluruh LeakingActivity (dan 32MB byte array) LEAK di heap!
}
```

### Kode Solutif: Clean, Safe, & Lifecycle-Aware

```kotlin
// SafeLifecycleActivity.kt (PRODUCTION-READY)
package com.enterprise.performance.fundamental

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch
import java.lang.ref.WeakReference

// Event hub yang aman dan thread-safe
object SafeSensorEventHub {
    private val _dataEvents = MutableSharedFlow<FloatArray>(extraBufferCapacity = 64)
    val dataEvents: SharedFlow<FloatArray> = _dataEvents.asSharedFlow()

    fun emitData(data: FloatArray) {
        _dataEvents.tryEmit(data)
    }
}

class SafeActivity : ComponentActivity() {

    // Gunakan backing field dengan ukuran dialokasikan sesuai lifecycle
    private var heavyResource: ByteArray? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        heavyResource = ByteArray(1024 * 1024 * 32)

        // Coroutine lifecycle scoping secara native membersihkan listener
        lifecycleScope.launch {
            // repeatOnLifecycle membatalkan eksekusi coroutine saat state berada di bawah STARTED
            // dan melanjutkan kembali saat state minimal STARTED
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                SafeSensorEventHub.dataEvents.collect { sensorData ->
                    processData(sensorData)
                }
            }
        }
    }

    private fun processData(data: FloatArray) {
        // Proses komputasi
    }

    override fun onDestroy() {
        super.onDestroy()
        // Melepaskan referensi manual jika memegang resource masif
        heavyResource = null
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Tinjauan mendalam mekanisme pencegahan kebocoran memori pada `SafeActivity.kt`:

1. `private val _dataEvents = MutableSharedFlow<FloatArray>(extraBufferCapacity = 64)`: Menggantikan implementasi observer manual berbasis raw list interface. `SharedFlow` menangani konkurensi antar-thread secara aman tanpa menyimpan referensi hard reference instance class observer secara eksplisit.
2. `lifecycleScope.launch`: Mengikat lifecycle coroutine runner langsung ke `LifecycleOwner` dari activity. Ketika activity mencapai state `DESTROYED`, scope ini secara otomatis memicu pembatalan (`cancel()`) pada semua *child jobs*.
3. `repeatOnLifecycle(Lifecycle.State.STARTED)`: Mekanisme suspensi suspensi deklaratif. Ketika Activity berpindah ke background (misalnya ditimpa Activity lain atau layar mati), flow collection ditangguhkan, melepaskan CPU resource dari pekerjaan pemrosesan data.
4. `heavyResource = null` di `onDestroy()`: Meskipun GC idealnya membersihkan seluruh Activity tree, komponen view hierarchy native (seperti bitmap buffers dan render nodes) sering mengalami latency pembersihan 1-2 siklus GC. Me-null-kan referensi byte array masif memastikan heap space langsung memenuhi kualifikasi reklamasi memori pada siklus Young Generation berikutnya.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: "High-Volume Real-Time Crypto Ticker Jank & OOM"
Pada sebuah aplikasi enterprise Financial/Fintech, terdapat halaman live dashboard yang menerima stream websocket harga 100 aset kripto dengan pembaruan frekuensi tinggi (~200 pesan per detik). 

**Simptom di Production:**
* Crash `OutOfMemoryError` (OOM) terjadi pada 4.2% sesi pengguna, terkonsentrasi pada perangkat low-to-mid range setelah 10-15 menit pemakaian terus-menerus.
* UI Jank parah: Render time rata-rata melonjak dari 7ms menjadi 42ms per frame (drop ke ~20 FPS) saat pengguna melakukan scrolling cepat pada list.

**Analisis Root Cause Menggunakan Memory Profiler & Perfetto:**
1. **Memory Churn Ekstrem:** Model parsing data websocket mengalokasikan ribuan objek DTO kecil per detik. Alokasi ini memicu ART Generational CC GC beroperasi non-stop (*mutator thread pause* berulang).
2. **Compose Unstable Recomposition:** Halaman dashboard menggunakan Jetpack Compose `LazyColumn`. Item list menerima model data class reguler yang memiliki properti `val tags: List<String>`. Compiler Compose menandai kelas ini sebagai *Unstable* karena `List` adalah interface JVM publik yang mutable implementation-nya tidak dapat dijamin. Akibatnya: Setiap kali harga satu koin berubah, *seluruh baris pada 100 elemen LazyColumn dieksekusi ulang* (bukan hanya baris yang berubah).
3. **Leaked Flow Collect Scope:** Event channel websocket di-collect pada coroutine scope independen (`GlobalScope`), menyebabkan Activity tidak pernah di-garbage collect saat pengguna menavigasi bolak-balik antara halaman Home dan Dashboard. 5 instance Activity tertahan di memory secara bersamaan.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi refactoring kelas produksi yang memecahkan masalah di atas menggunakan:
1. Stability annotation `@Immutable`.
2. Immutable collection collections.
3. Macrobenchmark test suite terisolasi.
4. Memory allocation tuning via pooling & primitives.

```kotlin
// ProductionTickerModels.kt
package com.enterprise.performance.crypto

import androidx.compose.runtime.Immutable
import kotlinx.collections.immutable.ImmutableList

// 1. ANNOTATE SEBAGAI IMMUTABLE UNTUK SKIPPING COMPOSE OPTIMIZATION
@Immutable
data class CryptoTickerUiState(
    val id: String,
    val symbol: String,
    val currentPriceUsd: Double,
    val changePercent24h: Float,
    val tags: ImmutableList<String> // Gunakan ImmutableList agar Compose Compiler menganggapnya stable
)
```

```kotlin
// OptimizedTickerItem.kt
package com.enterprise.performance.crypto

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun OptimizedTickerRow(
    ticker: CryptoTickerUiState,
    modifier: Modifier = Modifier
) {
    // Tidak ada alokasi objek baru di dalam composable body
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text(text = ticker.symbol, modifier = Modifier.weight(1f))
        Text(text = "$${ticker.currentPriceUsd}", modifier = Modifier.weight(1f))
        Text(
            text = "${ticker.changePercent24h}%",
            modifier = Modifier.weight(1f)
        )
    }
}
```

```kotlin
// Macrobenchmark Suite: Menjamin Tidak Terjadi Regresi Performa
// Lokasi: /benchmark/src/main/java/com/enterprise/benchmark/CryptoScrollBenchmark.kt
package com.enterprise.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.Until
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CryptoDashboardScrollBenchmark {

    @get:Rule
    val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun scrollDashboardListCompilationBaselineProfiles() = benchmarkRule.measureRepeated(
        packageName = "com.enterprise.performance",
        metrics = listOf(FrameTimingMetric()),
        compilationMode = CompilationMode.Partial(), // Simulasi Baseline Profiles
        iterations = 5,
        startupMode = StartupMode.WARM,
        setupBlock = {
            pressHome()
            startActivityAndWait()
            // Pastikan screen dashboard muncul dan websocket terhubung
            device.wait(Until.hasObject(By.res("crypto_list")), 5000)
        }
    ) {
        val list = device.findObject(By.res("crypto_list"))
        // Eksekusi simulasi scroll berulang kali untuk mengukur p90, p95, dan p99 frame drops
        list.setGestureMargin(device.displayWidth / 5)
        repeat(3) {
            list.scroll(Direction.DOWN, 0.8f)
            device.waitForIdle()
            list.scroll(Direction.UP, 0.8f)
            device.waitForIdle()
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter / Matriks | Manual Profiling (Android Studio) | LeakCanary Integration | Macrobenchmark / Microbenchmark |
| :--- | :--- | :--- | :--- |
| **Kebutuhan Setup** | Rendah (Langsung dari IDE, GUI) | Sangat Rendah (`debugImplementation`) | Menengah ke Tinggi (Module terpisah, device fisik) |
| **Overhead Performa** | Masif saat capturing Memory Dump & Trace | Menengah saat melakukan heap dump di background | Nol saat test berjalan (mengisolasi proses) |
| **Akurasi Metrik** | Kualitatif / Visual Inspection | Spesifik pada identifikasi GC Root Leaks | Kuantitatif (p50, p90, p99 millisecond execution time) |
| **Integrasi CI/CD** | Tidak praktis (bergantung operator manusia) | Parsial (bisa via test listener) | Native (Menghasilkan output JSON metrik per commit) |
| **Use Case Utama** | Deep-dive investigasi ad-hoc | Validasi leak saat QA/Staging testing | Proteksi regresi performa sebelum release prod |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. View Binding / Data Binding di Fragment Lifecycle
* **Pitfall:** Menyimpan referensi View Binding di property Fragment tanpa melepaskannya di `onDestroyView()`.
* **Mekanisme Kegagalan:** Fragment instance sering kali bertahan di backstack (hanya view hierarchy-nya yang dihancurkan). Memegang referensi root view mengunci seluruh view tree, fragment context, dan resources terkait di memori.
* **Mitigasi:** Gunakan pola auto-clearing binding atau override eksplisit:
  ```kotlin
  private var _binding: FragmentTickerBinding? = null
  private val binding get() = _binding!!

  override fun onDestroyView() {
      super.onDestroyView()
      _binding = null // CRITICAL
  }
  ```

### 2. Static Bitmaps & Hardware Acceleration Buffers
* **Pitfall:** Melakukan caching instansiasi `Bitmap` ke dalam memory map singleton tanpa batas alokasi.
* **Mekanisme Kegagalan:** Mulai Android 8.0, pixel data alokasi Bitmap disimpan pada native heap (`Graphics` memory). Native heap tidak memiliki batasan ketat seperti ART Java heap, namun jika sistem kehabisan native memory, proses akan di-SIGKILL instan oleh kernel Linux tanpa melempar Catchable Java OOM.
* **Mitigasi:** Gunakan pustaka image loading modern (Coil/Glide) yang mengelola LRU cache berbasis PSS budget, atau kelola `BitmapPool` secara terukur.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Mengira `CoroutineScope(Dispatchers.IO)` Menjamin Keamanan Leak
```kotlin
// KESALAHAN:
class UserSessionActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Coroutine ini tidak terikat pada lifecycle activity!
        CoroutineScope(Dispatchers.IO).launch {
            val data = apiService.fetchData()
            runOnUiThread { updateUI(data) } // Menahan referensi Activity
        }
    }
}
```
* **Solusi:** Selalu gunakan `lifecycleScope` pada Activity/Fragment, atau `viewModelScope` pada ViewModel.

### Mistake 2: Anonymous Inner Classes pada Handler/Runnables
```kotlin
// KESALAHAN:
class SplashActivity : AppCompatActivity() {
    private val handler = Handler(Looper.getMainLooper())
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Runnable memegang referensi implisit ke SplashActivity
        handler.postDelayed({
            navigateToHome()
        }, 30000) // Delay 30 detik. Jika user close activity, Splash tetap leak selama 30 detik!
    }
}
```
* **Solusi:** Hapus pesan pada lifecycle teardown via `handler.removeCallbacksAndMessages(null)` atau gunakan Coroutines dengan struktur delay yang dapat dibatalkan.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Adopsi Baseline Profiles:** Wajib mengompilasi DEX bytecode ke format AOT (Ahead-of-Time) sebelum aplikasi dijalankan pertama kali oleh end user. Ini memotong *startup latency* hingga 30-40%.
2. **Strict Stability Policy di Compose:** Semua class data transfer (DTO) yang melintasi layer UI harus bersifat immutable. Terapkan rule detektif Compose Compiler Metrics pada pipeline build:
   ```groovy
   tasks.withType(org.jetbrains.kotlin.gradle.tasks.KotlinCompile).configureEach {
       kotlinOptions {
           freeCompilerArgs += [
               "-P",
               "plugin:androidx.compose.compiler.plugins.kotlin:reportsDestination=" + project.buildDir.absolutePath + "/compose_metrics"
           ]
       }
   }
   ```
3. **Budget Profiling SLA:** Terapkan Service Level Agreement (SLA) performa dalam engineering team:
   * Cold Start: < 1200ms pada device tier bawah.
   * Frame Drop Rate: Kurang dari 1% frame melebihi batas 16ms saat scrolling standar.
   * Zero Retention Leaks: 0 toleransi terhadap kebocoran `Activity` atau `Fragment` yang dilaporkan oleh LeakCanary di pipeline QA automasi.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Optimasi Loop & Primitives di Hot Execution Paths
Hindari *auto-boxing* di path eksekusi yang intensif (seperti Canvas Custom Drawing atau pemrosesan stream data audio/kripto):

```kotlin
// BURUK: Menyebabkan ribuan alokasi java.lang.Integer / java.lang.Double di heap
val numbersList = ArrayList<Double>()

// OPTIMAL: Gunakan Android High-Performance Primitive Arrays
val primitiveArray = DoubleArray(capacity)
// Atau gunakan AndroidX Sparse Arrays untuk mapping integer tanpa overhead object Node:
val map = androidx.collection.SparseArrayCompat<String>()
```

### Trace Markers Menggunakan AndroidX Tracing
Tambahkan trace section manual untuk menampakkan blok eksekusi kritis secara eksplisit di timeline Perfetto/Systrace:

```kotlin
import androidx.tracing.trace

fun processLargeTransactionPayload(payload: ByteArray) {
    trace("processLargeTransactionPayload") {
        // Logika internal komputasi kompleks
        // Ini akan muncul sebagai slice bernama di Perfetto visualizer
    }
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Pembersihan Heap Dump Sanitization:** Heap dump (`.hprof`) mengandung seluruh snapshot memori, termasuk plain-text password, auth token, dan data pribadi pengguna (PII). **Jangan pernah menyematkan LeakCanary aktif di release build**. LeakCanary hanya boleh diintegrasikan pada variant `debug` atau `stagingInternal`:
   ```groovy
   dependencies {
       debugImplementation 'com.squareup.leakcanary:leakcanary-android:2.14'
   }
   ```
2. **Sanitasi Objek Sensitif:** Jika mengolah data kredensial/kriptografi, gunakan `CharArray` atau byte array yang dapat di-*wipe* secara manual menggunakan method overwrite (`Arrays.fill(charArray, '0')`) segera setelah selesai digunakan, alih-alih meletakkannya di `String` yang bersifat immutable dan tidak dapat dihapus instan dari memory heap.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### CLI Diagnostics via ADB
Staff Engineer wajib menguasai telemetri performa via Android Debug Bridge tanpa bergantung pada GUI:

* **Inspeksi Alokasi Memori Real-Time:**
  ```bash
  adb shell dumpsys meminfo com.enterprise.performance
  ```
  *Perhatikan kolom: `TOTAL PSS`, `Native Heap`, dan `Java Heap`.*

* **Mengukur Jank Frame Berbasis GFXINFO:**
  ```bash
  adb shell dumpsys gfxinfo com.enterprise.performance reset
  # [Lakukan skenario scrolling pada aplikasi di HP]
  adb shell dumpsys gfxinfo com.enterprise.performance framestats
  ```
  *Output memberikan data histografis mengenai jumlah frame yang melanggar batas VSYNC 16.6ms.*

* **Merekam System Trace Melalui Perfetto CLI:**
  ```bash
  python record_android_trace -o trace.perfetto-trace -t 10s -b 64mb sched freq idle am wm gfx view binder_driver
  ```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────┐
│                      PERFORMANCE TUNING CHEAT SHEET                    │
├────────────────────────────────────────────────────────────────────────┤
│ 1. MEMORY LEAKS IDENTIFICATION                                         │
│    - Look for: Static Context references, Uncancelled Coroutine scopes,│
│      View references inside long-living Singletons.                    │
│    - Tool: LeakCanary (Local QA), ADB Meminfo (CI).                    │
│                                                                        │
│ 2. RENDERING BUDGET                                                    │
│    - 60 FPS  = 16.6 ms / frame                                         │
│    - 90 FPS  = 11.1 ms / frame                                         │
│    - 120 FPS = 8.33 ms / frame                                         │
│                                                                        │
│ 3. COMPOSE STABILITY RULES                                             │
│    - Primitive types (Int, String, Boolean) -> Stable                  │
│    - Collections (List, Set, Map) -> UNSTABLE by default!              │
│    - Solution: Gunakan ImmutableList atau wrap dengan @Immutable.      │
│                                                                        │
│ 4. CRITICAL ADB COMMANDS                                               │
│    - Memory: `adb shell dumpsys meminfo <package>`                     │
│    - Jank:   `adb shell dumpsys gfxinfo <package>`                     │
│    - CPU:    `adb shell top -m 10`                                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Pilihan Ganda & Analisis

#### 1. Manakah dari komponen berikut yang merupakan GC Root di Android Runtime?
A. Objek `View` yang saat ini terpasang di window hierarchy.  
B. Objek Java `Thread` yang sedang berjalan aktif.  
C. Primitive value `Int` di dalam method lokal yang sudah selesai dieksekusi.  
D. Objek weak reference (`WeakReference<Context>`).  

#### 2. Mengapa penggunaan `List<T>` standar pada data class UI state Compose sering menyebabkan recomposition yang tidak perlu?
A. Compiler Compose melarang pembacaan List di dalam scope composable.  
B. Kotlin `List` adalah interface publik yang tidak menjamin immutabilitas implementasi dasarnya, sehingga dievaluasi sebagai *Unstable*.  
C. Slot Table tidak dapat mengalokasikan memori untuk class bertipe dynamic collections.  
D. `List` secara otomatis memicu garbage collection setiap kali item baru ditambahkan.  

#### 3. Apa implikasi performa terbesar jika mutator thread (aplikasi) mengalokasikan objek baru dengan kecepatan yang melampaui kemampuan Concurrent Copying GC?
A. Perangkat akan langsung me-reboot Linux kernel secara otomatis.  
B. Objek akan otomatis dialokasikan di swap disk memory.  
C. ART akan memaksa mutator thread untuk melakukan alokasi blocking/pause untuk membantu kerja GC, mengakibatkan UI jank parah.  
D. Sistem operasi mematikan proses via SIGSEGV.  

#### 4. Kapan waktu yang tepat untuk melakukan pelepasan referensi binding (`_binding = null`) pada implementasi View Binding di Fragment?
A. Di `onStop()`  
B. Di `onDestroyView()`  
C. Di `onDestroy()`  
D. Di `onDetach()`  

#### 5. Apa perbedaan utama antara metrik Resident Set Size (RSS) dan Proportional Set Size (PSS)?
A. PSS mencakup memori virtual, sedangkan RSS hanya memori fisik.  
B. PSS memperhitungkan pembagian proporsional dari shared libraries bersama proses lain, sedangkan RSS menghitung keseluruhan shared libraries secara penuh untuk setiap proses.  
C. RSS hanya mencatat Native Heap, sedangkan PSS mencatat Java Heap.  
D. PSS adalah kalkulasi GPU VRAM, sedangkan RSS adalah kalkulasi DRAM CPU.  

---

### Kunci Jawaban & Evaluasi

1. **Jawaban: B.** Active threads (thread yang sedang berjalan) dievaluasi oleh runtime sebagai root traversal pemindaian memori. Selama thread hidup, seluruh referensi rantai objek yang dipegang oleh thread tersebut tidak dapat dibersihkan.
2. **Jawaban: B.** `List` di Kotlin standar adalah read-only interface, bukan *immutable*. Class yang mengimplementasikannya bisa saja mutable (`ArrayList`). Karena compiler tidak dapat memverifikasi immutabilitasnya saat compile-time, parameter tersebut dianggap unstable, menggugurkan optimasi smart-recomposition skipping.
3. **Jawaban: C.** Saat laju alokasi menguras ketersediaan heap sebelum background GC selesai, ART menerapkan *mutator-assisted pause*. Thread utama aplikasi dipaksa berhenti bekerja untuk membersihkan memori, menghasilkan frame drop masif.
4. **Jawaban: B.** Fragment view hierarchy dihancurkan saat siklus hidup mencapai `onDestroyView()`, namun instance Fragment dapat tetap hidup di memory (misalnya di backstack). Melepaskan referensi di `onDestroyView()` adalah keharusan mutlak untuk mencegah kebocoran memori View.
5. **Jawaban: B.** RSS menyesatkan untuk multi-process architecture karena menduplikasi alokasi shared libraries (misal: zyg