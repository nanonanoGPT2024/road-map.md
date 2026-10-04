# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesialisasi:** Android Engineering
*   **Bab / Modul:** Bab 07 / Module 01
*   **Judul Modul:** Asynchronous Background Processing & WorkManager
*   **Tingkat Kerumitan:** Advanced / Production-Grade
*   **Prasyarat Pengetahuan:** Kotlin Coroutines (Scopes, Dispatchers, Contexts, Cancellation), Android Process Lifecycle, Android Architecture Components, SQLite/Room persistence, Dagger/Hilt Dependency Injection.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Mendekomposisi dan Mengkategorikan Kebutuhan Background Processing:** Membedakan skenario eksekusi *Immediate*, *Deferred*, dan *Exact/Alarm-based* pemrosesan latar belakang sesuai dengan Android Battery Optimization Guidelines (Doze Mode, App Standby Buckets).
2.  **Menganalisis Mekanisme Internal WorkManager:** Menjelaskan alur kerja dari *enqueue* ke eksekusi, interaksi SQLite via Room (`androidx.work.impl.WorkDatabase`), serta pemilihan orkestrasi runtime antara `JobScheduler`, `JobServiceEngine`, dan fallback `AlarmManager + BroadcastReceiver`.
3.  **Mengimplementasikan Asynchronous Execution via CoroutineWorker:** Membangun unit kerja yang aman dari *thread-blocking* menggunakan Kotlin Coroutines, memetakan *cooperative cancellation*, serta mengintegrasikan *Constraints* sistem operasi secara presisi.
4.  **Membangun Dependency Injection Pipeline untuk Worker:** Melakukan refactoring *default worker factory* menjadi Hilt-assisted injection (`@HiltWorker`) untuk menginjeksi service dan repository enterprise ke dalam lifecycle runtime worker.
5.  **Merancang Rantai Tugas Kompleks (Chaining & Parallel Orchestration):** Mengabstraksi alur dependensi pekerjaan multi-tahap (seperti Image Pre-processing $\to$ Chunking $\to$ Upload $\to$ Clean-up) menggunakan `beginWith(...)`, `then(...)`, `combine(...)`, dan menangani resolusi konflik via `ExistingWorkPolicy`.
6.  **Memitigasi Edge Cases Sistem Operasi:** Menangani terminasi paksa OS, timeout eksekusi 10 menit, Foreground Service Type requirement di Android 14+ (API 34+), transmisi payload data besar via Room/File storage, dan Battery Saver aggressive OEM policies.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam ekosistem Android modern, background processing tidak lagi didefinisikan sebagai "menjalankan kode di thread selain UI". Mental model yang benar adalah **Process State & OS Contract Management**. 

Aplikasi Android bukan entitas monolitik yang terus berjalan. Komponen aplikasi (Activity, Service) hanyalah *entry points* bagi sistem operasi Linux di bawahnya untuk menentukan apakah proses Anda layak hidup atau harus dimatikan demi efisiensi daya baterai dan alokasi RAM.

```
       Prioritas Memori Rendah                           Prioritas Memori Tinggi
[ Cached / Killed Process ] <------ [ Background ] <------ [ Foreground Process ]
        ^                                 |
        |---- Dimatikan saat Low-Memory --|
```

Ketika aplikasi berpindah ke background, lifecycle process Anda masuk ke zona terminasi OS. Jika Anda meluncurkan pekerjaan jangka panjang (long-running) hanya dengan `CoroutineScope(Dispatchers.IO).launch` di dalam ViewModel atau lifecycle komponen UI, pekerjaan tersebut **dijamin akan mati** begitu proses dimusnahkan oleh *Low Memory Killer (LMK)*.

Mental model WorkManager adalah: **Pekerjaan yang Dijamin Berjalan (Guaranteed Execution), Bukan Pekerjaan Real-Time.** 

WorkManager adalah sebuah lapisan persisten (*persistence-first scheduler*). Pekerjaan yang Anda daftarkan (*enqueued*) dicatat secara atomik ke dalam database relasional internal (SQLite) sebelum runtime sistem diinstruksikan untuk mengeksekusinya. Jika baterai habis, perangkat *reboot*, atau memori drop, status pekerjaan tetap tersimpan dan dieksekusi kembali ketika sistem operasi telah memenuhi kondisi (*Constraints*) yang Anda tetapkan.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Interaksi Komponen Internal WorkManager

```
+---------------------------------------------------------------------------------------+
|                                    APPLICATION LAYER                                  |
|                                                                                       |
|  [ WorkRequest ] -----> [ WorkManager.getInstance() ]                                 |
|   (Constraints, Data)              |                                                  |
+------------------------------------|--------------------------------------------------+
                                     | enqueue()
                                     v
+---------------------------------------------------------------------------------------+
|                                  WORKMANAGER CORE                                     |
|                                                                                       |
|  +--------------------+       Write Transaction        +---------------------------+  |
|  | WorkContinuation / | -----------------------------> | WorkDatabase (Room/SQLite)|  |
|  | Schedulers Engine  |                                | Stores: State, Worker,    |  |
|  +--------------------+                                | InputData, Constraints    |  |
|           |                                            +---------------------------+  |
|           | Evaluate Device API Level & State                        |                |
|           v                                                          v                |
+-----------|----------------------------------------------------------|----------------+
            |                                                          | Read Specs
            v                                                          v
+---------------------------------------------------------------------------------------+
|                              OS SCHEDULING SUBSYSTEM                                  |
|                                                                                       |
|   API >= 23:                                                                          |
|   +-------------------------------------------------------------------------------+   |
|   | JobScheduler.schedule()  --> System JobService Proxy                          |   |
|   +-------------------------------------------------------------------------------+   |
|                                                                                       |
|   API < 23 (Fallback Lifecycle):                                                      |
|   +-------------------------------------------------------------------------------+   |
|   | AlarmManager + BroadcastReceiver (Reschedule via System Alarm)                |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
                                     |
                                     | Trigger based on Constraints
                                     v
+---------------------------------------------------------------------------------------+
|                            EXECUTION LAYER (Runtime)                                  |
|                                                                                       |
|  [ System Job/Intent ] ---> [ androidx.work.impl.background.systemjob.SystemJobService]
|                                    |                                                  |
|                                    v                                                  |
|                      [ androidx.work.impl.Processor ]                                 |
|                                    |                                                  |
|                 +------------------+------------------+                               |
|                 | (Assisted Injection / WorkerFactory)|                               |
|                 v                                     v                               |
|       [ Custom Worker Thread ]             [ CoroutineWorker Scope ]                  |
|                 |                                     |                               |
|                 v                                     v                               |
|          doWork(): Result                      doWork(): Result                       |
|                 \                                     /                               |
|                  +-----------------+-----------------+                                |
|                                    |                                                  |
|                                    v                                                  |
|           Persist SUCCESS / RETRY / FAILURE ke WorkDatabase                           |
+---------------------------------------------------------------------------------------+
```

### Alur Eksekusi: Dari Enqueue Hingga Selesai

```
[Enqueue WorkRequest]
       │
       ▼
[Buka Transaksi SQLite] ──> Tulis WorkerSpec ke WorkDatabase (State: ENQUEUED)
       │
       ▼
[Kirim ke System Scheduler]
       │
       ├─► Jika Constraints TERPENUHI langsung ───┐
       │                                         │
       └─► Jika Constraints TIDAK TERPENUHI      │
                 │                               │
                 ▼                               │
           [Tidur/Idle]                          │
                 │ (OS Event: Charging/Net ON)   │
                 ▼                               │
       [Bangun via OS Hook] ◄────────────────────┘
                 │
                 ▼
       [Instansiasi Worker via WorkerFactory]
                 │
                 ▼
       [Panggil CoroutineWorker.doWork()] ─── Dispatcher.IO
                 │
         ┌───────┴────────────────────────┐
         │                                │
      [Sukses]                        [Eksepsi]
         │                                │
         ▼                                ▼
  Result.success()             Evaluasi Backoff Policy
         │                                │
         │                                ├─► Result.retry() ──> Jadwalkan Ulang (Backoff)
         │                                │
         │                                └─► Result.failure() ─> State: FAILED
         ▼
  Update DB: State = SUCCEEDED
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Database Internal: `WorkDatabase`
WorkManager adalah state machine berbasis Room. Setiap kali Anda memanggil `enqueue()`, WorkManager tidak langsung membuat thread. WorkManager mengeksekusi *insert query* ke dalam tabel internal:
*   `WorkSpec`: Menyimpan state saat ini (`ENQUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `BLOCKED`, `CANCELLED`), class name dari Worker, batasan (*constraints*), backoff delay, dan metadata runtime.
*   `WorkTag`: Pemetaan ID unik terhadap tag kustom untuk query massal.
*   `WorkName`: Pemetaan nama unik untuk penanganan *UniqueWork*.
*   `SystemIdInfo`: Pemetaan relasional ID WorkManager internal ke ID `JobScheduler` OS.
*   `Dependency`: Hubungan prerequisit DAG (*Directed Acyclic Graph*) antar-worker.

### 2. Runtime Selection Logic
WorkManager mengevaluasi kemampuan kernel dan sistem operasi untuk memutuskan engine mana yang digunakan:
*   **Android 6.0 (API 23) ke atas:** Menggunakan `SystemJobScheduler` bawaan platform yang langsung berkomunikasi dengan framework service `JobScheduler`. Ini mematuhi aturan Doze Mode dan meminimalkan konsumsi daya baterai.
*   **Android 5.x (API 21-22):** Secara historis menggunakan implementasi kustom `JobScheduler` berbasis Play Services jika tersedia, atau transisi internal.
*   **Legacy Fallback (< API 23):** Memadukan `AlarmManager` untuk membangunkan CPU, dan `BroadcastReceiver` yang memantau perubahan status konektivitas (`CONNECTIVITY_ACTION`) atau status baterai, lalu mengeksekusi worker secara manual.

### 3. State Machine & Transisi Siklus Hidup
Transisi siklus hidup sebuah `WorkRequest` berjalan deterministik:

```
[BLOCKED] ──────> [ENQUEUED] <═══════════════╗
                     │                       ║
                     │ Constraints terpenuhi ║
                     ▼                       ║
                 [RUNNING]                   ║ Result.retry()
                     │                       ║
        ┌────────────┼────────────┐          ║
        │            │            │          ║
        ▼            ▼            ▼          ║
   [SUCCEEDED]    [FAILED]   [CANCELLED]     ║
   (Terminal)    (Terminal)  (Terminal)      ║
                                             ║
        └────────────────────────────────────╝
```

*   **BLOCKED:** Menunggu worker induk dalam graph/chain selesai dieksekusi dengan status `SUCCEEDED`.
*   **ENQUEUED:** Siap dijalankan segera setelah scheduler sistem menyatakan batasan (*constraints*) terpenuhi.
*   **RUNNING:** Worker aktif dan kodenya sedang berjalan di background thread.
*   **SUCCEEDED / FAILED / CANCELLED:** State terminal (final). Data hasil eksekusi (`outputData`) disimpan di SQLite dan dapat diamati via `LiveData` atau `Flow`.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Batasan Sistem: Doze Mode & Standby Buckets
Sejak Android 6.0 (Marshmallow), Google memperkenalkan **Doze Mode**. Jika perangkat tidak tersambung ke charger, layar mati, dan diam (*motionless*) selama beberapa waktu, OS mematikan akses jaringan background, mengabaikan wakelocks, dan menunda eksekusi sinkronisasi.

Di Android 9.0 (Pie), OS memperkenalkan **App Standby Buckets**:
*   *Active*: Aplikasi sedang digunakan. Tidak ada penalti.
*   *Working Set*: Sering digunakan. Penundaan minimal.
*   *Frequent*: Digunakan berkala. Pekerjaan background ditunda lebih lama.
*   *Rare*: Jarang digunakan. Background restrictions ketat (eksekusi hanya beberapa jam sekali).
*   *Restricted*: Diperkenalkan di API 30+, penalti paling agresif, akses jaringan ditangguhkan.

WorkManager memahami sistem ini. Ketika sistem memasuki *maintenance window* Doze Mode, WorkManager mengekstrak pekerjaan yang telah diantrekan dan mengeksekusinya secara batch, mencegah aktivasi CPU radio berulang kali (*radio tail energy drain*).

### Batasan Waktu Eksekusi: 10-Minute Execution Window
Sebuah worker non-foreground dibatasi oleh OS: **maksimum 10 menit waktu eksekusi terus-menerus**. Jika lewat dari batas tersebut:
1.  Sistem mengirimkan sinyal interupsi ke worker.
2.  `CoroutineWorker` akan menerima pembatalan Coroutine (`CancellationException`).
3.  Jika worker tidak merespons dan melepaskan resource dalam waktu beberapa detik, OS akan menandai status pekerjaannya gagal, atau pada implementasi legacy dapat menyebabkan Application Not Responding (ANR) pada komponen Background.

Jika Anda membutuhkan durasi tanpa batas (misal: export video besar atau sinkronisasi 1 jam), worker **harus dipromosikan ke Foreground Service** via WorkManager `setForeground(ForegroundInfo)`.

### Backoff Policies & Truncated Exponential Backoff
Ketika operasi transient (misal: koneksi API putus) terjadi, Anda mengembalikan `Result.retry()`. WorkManager menghitung waktu penundaan berdasarkan rumus:

$$\text{Delay}_{\text{Linear}} = \text{InitialDelay} \times \text{attempt}$$

$$\text{Delay}_{\text{Exponential}} = \text{InitialDelay} \times 2^{(\text{attempt} - 1)}$$

Batas minimum delay yang didukung sistem operasi adalah **10 detik**. WorkManager membatasi penundaan maksimum (*truncated ceiling*) secara internal hingga maksimal **5 jam**.

### Input/Output Data Payload Constraints: Batasan 10KB
Payload yang dilewatkan ke `Data.Builder()` disimpan langsung di tabel SQLite `WorkDatabase`. Mengingat Room mengalokasikan data ini dalam Android IPC Cursor Window (yang memiliki ukuran batas aman 2MB untuk seluruh operasi kursor), WorkManager memberlakukan batas keras: **10.240 byte (10 KB)**.

Mencoba menyimpan payload base64 gambar atau JSON string besar ke dalam `Data.Builder` akan melempar:
`IllegalStateException: Data cannot occupy more than 10240 bytes when serialized`

Solusi arsitektural: Gunakan SQLite (Room) atau File Cache internal, dan hanya lewatkan `fileUri` atau `primaryKeyId` (UUID/Long) melalui `workDataOf()`.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bertahap dari sebuah `CoroutineWorker` untuk memproses kompresi data file secara asinkron.

### Langkah 1: Tambahkan Dependensi Gradle (KTS)
```kotlin
// build.gradle.kts
dependencies {
    val workVersion = "2.9.0"
    implementation("androidx.work:work-runtime-ktx:$workVersion")
}
```

### Langkah 2: Definisikan Unit Kerja (`CompressLogWorker.kt`)
```kotlin
package com.enterprise.workdemo.workers

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.zip.GZIPOutputStream

class CompressLogWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    companion object {
        const val KEY_INPUT_LOG_PATH = "key_input_log_path"
        const val KEY_OUTPUT_COMPRESSED_PATH = "key_output_compressed_path"
        const val KEY_ERROR_MESSAGE = "key_error_message"
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val inputPath = inputData.getString(KEY_INPUT_LOG_PATH)
            ?: return@withContext Result.failure(
                workDataOf(KEY_ERROR_MESSAGE to "Missing input log path")
            )

        val inputFile = File(inputPath)
        if (!inputFile.exists() || !inputFile.canRead()) {
            return@withContext Result.failure(
                workDataOf(KEY_ERROR_MESSAGE to "Target log file does not exist or unreadable")
            )
        }

        val outputFile = File(applicationContext.cacheDir, "compressed_${inputFile.nameWithoutExtension}.gz")

        try {
            compressFileGzip(inputFile, outputFile)
            
            // Mengirim hasil ke chaining worker selanjutnya
            val outputData = workDataOf(KEY_OUTPUT_COMPRESSED_PATH to outputFile.absolutePath)
            Result.success(outputData)
        } catch (ioe: IOException) {
            // Sinyal masalah jaringan/file locks sementara; rekomendasikan retry
            Result.retry()
        } catch (e: Exception) {
            Result.failure(workDataOf(KEY_ERROR_MESSAGE to (e.localizedMessage ?: "Unknown compression error")))
        }
    }

    private fun compressFileGzip(source: File, destination: File) {
        source.inputStream().buffered().use { input ->
            FileOutputStream(destination).buffered().let { fos ->
                GZIPOutputStream(fos).buffered().use { gzipOut ->
                    input.copyTo(gzipOut)
                }
            }
        }
    }
}
```

### Langkah 3: Mengonfigurasi Constraints dan Enqueue Worker
```kotlin
package com.enterprise.workdemo

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.enterprise.workdemo.workers.CompressLogWorker
import java.io.File
import java.util.concurrent.TimeUnit

class LogSyncManager(private val context: Context) {

    fun triggerLogCompression(logFile: File) {
        val constraints = Constraints.Builder()
            .setRequiresBatteryNotLow(true)
            .setRequiresStorageNotLow(true)
            .build()

        val inputData = workDataOf(
            CompressLogWorker.KEY_INPUT_LOG_PATH to logFile.absolutePath
        )

        val compressRequest = OneTimeWorkRequestBuilder<CompressLogWorker>()
            .setConstraints(constraints)
            .setInputData(inputData)
            .setBackoffCriteria(
                backoffPolicy = BackoffPolicy.EXPONENTIAL,
                backoffDelay = 15,
                timeUnit = TimeUnit.SECONDS
            )
            .addTag("LOG_MAINTENANCE_WORK")
            .build()

        WorkManager.getInstance(context).enqueue(compressRequest)
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi arsitektural terhadap implementasi di atas:

1.  `class CompressLogWorker(...) : CoroutineWorker(appContext, params)`: 
    *   Mewarisi `CoroutineWorker` alih-alih `Worker` standar. 
    *   `Worker` primitif mengeksekusi method `doWork()` secara sinkron di thread pool bawaan WorkManager (`SynchronousExecutor`). `CoroutineWorker` menyediakan lingkungan coroutine murni yang terikat pada `Dispatchers.Default` secara otomatis, tetapi aman dialihkan.
2.  `override suspend fun doWork(): Result = withContext(Dispatchers.IO)`:
    *   Mengalihkan context secara eksplisit ke IO Dispatcher, mencegah pemblokiran thread default WorkManager saat operasi I/O stream file intensif berlangsung.
3.  `val inputPath = inputData.getString(...) ?: return@withContext Result.failure(...)`:
    *   Pemeriksaan defensif. Jika data esensial tidak dikirimkan oleh pemanggil, worker langsung membatalkan eksekusi dengan status `Result.failure()` agar sistem tidak menyia-nyiakan baterai untuk melakukan retry yang mustahil berhasil.
4.  `source.inputStream().buffered().use { ... }`:
    *   Pola pemanfaatan AutoCloseable via ekstensi Kotlin `.use`. Ini menjamin file descriptor segera ditutup bahkan jika coroutine dibatalkan di tengah jalan (*cancellation triggered*), mencegah *memory leak* dan *file lock retention*.
5.  `catch (ioe: IOException) { Result.retry() }`:
    *   Strategi pemisahan exception. Exception transient (konektivitas, I/O sementara) dialihkan ke `Result.retry()`, yang akan memicu `BackoffPolicy`. Exception fatal lainnya (seperti `IllegalArgumentException` atau `SecurityException`) langsung dikirim ke `Result.failure()`.
6.  `Constraints.Builder().setRequiresBatteryNotLow(true)...`:
    *   Menyatakan ke WorkManager bahwa jika level baterai perangkat berada di bawah ambang batas OS (umumnya di bawah 15-20%), eksekusi ditunda sampai pengisi daya dipasang atau baterai naik kembali.
7.  `.setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)`:
    *   Menginstruksikan scheduler bahwa jika `Result.retry()` dilempar, tunggu $15 \times 2^0 = 15$ detik untuk percobaan ke-2, $15 \times 2^1 = 30$ detik untuk percobaan ke-3, $60$ detik untuk percobaan ke-4, dan seterusnya.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: "Off-Grid Field Telemetry and Diagnostic Sync"
Sebuah perusahaan logistik skala global memiliki 10.000 perangkat Android khusus (rugged devices) yang dibawa oleh supir truk pengantar barang. 
*   **Tantangan Lapangan:** Supir melintasi daerah pelosok tanpa sinyal seluler selama berjam-jam (*offline first*).
*   **Kebutuhan:** Setiap kali paket diserahkan, supir memindai paket, merekam koordinat GPS akurat, dan mengambil foto tanda tangan penerima beresolusi tinggi.
*   **Batasan Teknis:**
    1.  Data telemetri dan foto harus diunggah ke server AWS S3 & REST backend hanya jika ada koneksi jaringan stabil tanpa membebani tagihan data kuota seluler roaming jika Wi-Fi tersedia (atau minimal koneksi *unmetered*).
    2.  Jika aplikasi di-kill paksa oleh OS karena pemakaian aplikasi navigasi (Google Maps) yang memakan RAM besar, proses sync data tanda tangan tidak boleh hilang atau rusak.
    3.  Aplikasi harus mengimplementasikan Hilt untuk mempermudah unit testing repositori jaringan.
    4.  Jika unggahan gagal di tengah jalan, berkas gambar tidak boleh diunggah ulang dari awal jika chunking didukung, atau harus memanfaatkan deduplikasi upload via idempotency token.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi ini mengombinasikan **Hilt Assisted Injection**, **Foreground Execution**, **Complex Work Chaining**, dan **Constraints**.

### 1. Inisialisasi Custom WorkManager dengan Hilt
Secara default, WorkManager diinisialisasi otomatis via startup content provider bawaan. Untuk mengintegrasikan Hilt, kita wajib mematikan default initializer dan menerapkan `Configuration.Provider`.

**AndroidManifest.xml**
```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />

    <application
        android:name=".TelemetryApplication"
        android:allowBackup="false"
        android:label="Enterprise Field Sync">

        <service
            android:name="androidx.work.impl.foreground.SystemForegroundService"
            android:foregroundServiceType="dataSync"
            tools:node="merge" />

        <!-- Matikan Default WorkManager Initializer -->
        <provider
            android:name="androidx.startup.InitializationProvider"
            android:authorities="${applicationId}.androidx-startup"
            android:exported="false"
            tools:node="merge">
            <meta-data
                android:name="androidx.work.WorkManagerInitializer"
                android:value="androidx.startup"
                tools:node="remove" />
        </provider>

    </application>
</manifest>
```

**TelemetryApplication.kt**
```kotlin
package com.enterprise.fieldsync

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class TelemetryApplication : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .setMinimumLoggingLevel(android.util.Log.INFO)
            .build()
}
```

### 2. Dependency Injection Interface & Fake Repositories
```kotlin
package com.enterprise.fieldsync.data

import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

data class TelemetryPayload(val transactionId: String, val signaturePath: String)

interface TelemetryRepository {
    suspend fun optimizeImage(rawImage: File): File
    suspend fun uploadTelemetryData(transactionId: String, optimizedImage: File): Boolean
}

@Singleton
class TelemetryRepositoryImpl @Inject constructor() : TelemetryRepository {
    override suspend fun optimizeImage(rawImage: File): File {
        // Simulasi optimasi/kompresi gambar
        return rawImage
    }

    override suspend fun uploadTelemetryData(transactionId: String, optimizedImage: File): Boolean {
        // Simulasi network latency & upload payload
        kotlinx.coroutines.delay(2000)
        return true
    }
}
```

### 3. Hilt-Injected Worker 1: Optimasi Gambar
```kotlin
package com.enterprise.fieldsync.workers

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.enterprise.fieldsync.data.TelemetryRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

@HiltWorker
class OptimizeSignatureWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val repository: TelemetryRepository
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        const val KEY_IN_FILE_PATH = "in_raw_path"
        const val KEY_OUT_OPTIMIZED_PATH = "out_opt_path"
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val rawPath = inputData.getString(KEY_IN_FILE_PATH) ?: return@withContext Result.failure()
        val file = File(rawPath)

        if (!file.exists()) {
            return@withContext Result.failure(workDataOf("error" to "Raw file missing"))
        }

        return@withContext try {
            val optimizedFile = repository.optimizeImage(file)
            Result.success(workDataOf(KEY_OUT_OPTIMIZED_PATH to optimizedFile.absolutePath))
        } catch (e: Exception) {
            Result.retry()
        }
    }
}
```

### 4. Hilt-Injected Worker 2: Foreground-Capable Upload Worker
```kotlin
package com.enterprise.fieldsync.workers

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.enterprise.fieldsync.data.TelemetryRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

@HiltWorker
class UploadTelemetryWorker @AssistedInject constructor(
    @Assisted private val appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val repository: TelemetryRepository
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        const val KEY_TRANSACTION_ID = "key_tx_id"
        const val CHANNEL_ID = "sync_channel"
        const val NOTIFICATION_ID = 9001
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val txId = inputData.getString(KEY_TRANSACTION_ID) ?: return@withContext Result.failure()
        val imagePath = inputData.getString(OptimizeSignatureWorker.KEY_OUT_OPTIMIZED_PATH)
            ?: return@withContext Result.failure()

        // Naikkan level menjadi Foreground Work jika upload diprediksi memakan waktu lama
        promoteToForeground()

        val uploadSuccess = try {
            repository.uploadTelemetryData(txId, File(imagePath))
        } catch (e: Exception) {
            return@withContext Result.retry()
        }

        if (uploadSuccess) {
            Result.success(workDataOf("status" to "SYNCED_AT_${System.currentTimeMillis()}"))
        } else {
            Result.retry()
        }
    }

    private suspend fun promoteToForeground() {
        createNotificationChannel()
        val notification = createNotification("Mengunggah log telemetri & bukti pengiriman...")
        
        val foregroundInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(
                NOTIFICATION_ID, 
                notification, 
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            ForegroundInfo(NOTIFICATION_ID, notification)
        }
        
        setForeground(foregroundInfo)
    }

    private fun createNotification(content: String): Notification {
        return NotificationCompat.Builder(appContext, CHANNEL_ID)
            .setContentTitle("Enterprise Delivery Sync")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Telemetri Data Synchronization",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = appContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }
}
```

### 5. Orchestrator Pipeline (Sequential & Unique Chaining)
```kotlin
package com.enterprise.fieldsync

import android.content.Context
import androidx.lifecycle.LiveData
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequest
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.enterprise.fieldsync.workers.OptimizeSignatureWorker
import com.enterprise.fieldsync.workers.UploadTelemetryWorker
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TelemetrySyncCoordinator @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val workManager = WorkManager.getInstance(context)

    fun dispatchSyncWorkflow(transactionId: String, rawSignatureFile: File): LiveData<WorkInfo> {
        val uniqueWorkName = "workflow_telemetry_$transactionId"

        // Batasan Step 1: Eksekusi kompresi di local tanpa butuh internet
        val localConstraints = Constraints.Builder()
            .setRequiresStorageNotLow(true)
            .build()

        val optimizeRequest = OneTimeWorkRequestBuilder<OptimizeSignatureWorker>()
            .setConstraints(localConstraints)
            .setInputData(workDataOf(OptimizeSignatureWorker.KEY_IN_FILE_PATH to rawSignatureFile.absolutePath))
            .build()

        // Batasan Step 2: Upload WAJIB ada koneksi terhubung & baterai cukup
        val networkConstraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .setRequiresBatteryNotLow(true)
            .build()

        val uploadRequest = OneTimeWorkRequestBuilder<UploadTelemetryWorker>()
            .setConstraints(networkConstraints)
            .setInputData(workDataOf(UploadTelemetryWorker.KEY_TRANSACTION_ID to transactionId))
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                WorkRequest.MIN_BACKOFF_MILLIS,
                TimeUnit.MILLISECONDS
            )
            .build()

        // Eksekusi Berantai Terproteksi UniqueWork:
        // KEEP: Abaikan jika sync untuk transaksi ini sedang berjalan
        workManager.beginUniqueWork(
            uniqueWorkName,
            ExistingWorkPolicy.KEEP,
            optimizeRequest
        ).then(uploadRequest)
         .enqueue()

        // Return status observabilitas Step 2 untuk UI
        return workManager.getWorkInfoByIdLiveData(uploadRequest.id)
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Dimensi | `CoroutineScope(Dispatchers.IO)` | `Foreground Service` Murni | `JobScheduler` Native | `WorkManager` (Jetpack) |
| :--- | :--- | :--- | :--- | :--- |
| **Batas Garansi Eksekusi** | **Sangat Rendah.** Terbunuh instan jika proses mati. | **Tinggi.** Selama notifikasi ada, tapi rentan OOM killer/ANR. | **Tinggi.** Dijamin OS, tapi API $\ge$ 21 only. | **Paling Tinggi.** Persisten via SQLite, survival antar reboot. |
| **Tingkat Kompleksitas** | Sangat Mudah (1 baris kode).