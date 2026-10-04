# Kurikulum Enterprise Android Engineering
## Bab 07: Asynchronous Background Processing & WorkManager
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, tech lead dan senior mobile engineer diharapkan mampu:
- Mendiagnosis dan mengimplementasikan arsitektur *background task execution* yang tangguh (*fault-tolerant*) pada ekosistem Android modern (API 26 hingga API 34+).
- Mengintegrasikan WorkManager dengan Dependency Injection (Hilt) menggunakan `@HiltWorker` dan `AssistedInject` tanpa melanggar prinsip *Inversion of Control*.
- Mengorkestrasi pipeline pekerjaan kompleks (*chained tasks*, *parallel branch-merge execution*) menggunakan `InputMerger` dan mitigasi limitasi payload data.
- Menangani pekerjaan dengan durasi panjang (*long-running background jobs*) secara aman menggunakan `ForegroundInfo`, adaptasi *Foreground Service Launch Restrictions* (Android 12+), serta *Foreground Service Types* (Android 14+).
- Menerapkan strategi *idempotency*, toleransi *system kill*, penyesuaian terhadap *App Standby Buckets* dan *Doze Mode*, serta validasi pengujian otomatis menggunakan `WorkManagerTestInitHelper`.

---

### 2. Prerequisite
Untuk memahami materi secara optimal, engineer wajib menguasai:
- **Kotlin Coroutines & Flow**: Lifecycle cancellation, Structured Concurrency, `CoroutineScope`, `SupervisorJob`, dan Dispatchers.
- **Dependency Injection**: Hilt/Dagger 2, Subcomponents, Factory Pattern, dan Assisted Injection.
- **Android Architecture Components**: ViewModel, Room Database, Lifecycle-aware components.
- **Android OS Internals**: Binder IPC, Broadcast Mechanism, Battery Optimization Lifecycle (Doze Mode, App Standby Buckets).

---

### 3. Concept & Internal Architecture (Mendalam)

WorkManager bukan sekadar *wrapper thread*, melainkan *engine orchestrator* deklaratif yang menjamin eksekusi tugas (*guaranteed execution*) meskipun aplikasi ditutup, sistem melakukan *restart*, atau perangkat mengalami kekurangan daya.

```
+-------------------------------------------------------------------------------+
|                             Application Layer                                 |
|   WorkRequest (Constraints, Backoff, Tags) -> Enqueued via WorkManagerImpl    |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|                       WorkManager Internal Engine                             |
|  +-------------------------------------------------------------------------+  |
|  | WorkDatabase (Room / SQLite)                                            |  |
|  | - Menyimpan state: ENQUEUED, RUNNING, SUCCEEDED, FAILED, BLOCKED        |  |
|  | - Menjamin State Persistence & Re-enqueue saat boot / app crash         |  |
|  +------------------------------------+------------------------------------+  |
|                                       |                                       |
|  +------------------------------------v------------------------------------+  |
|  | Schedulers Delegation Layer                                             |  |
|  | - GreedyScheduler      : Eksekusi in-process saat constraint terpenuhi  |  |
|  | - SystemJobScheduler   : Delegasi ke OS JobScheduler (API >= 23)        |  |
|  | - SystemAlarmScheduler : Delegasi via AlarmManager + Broadcast (Legacy)|  |
|  +------------------------------------+------------------------------------+  |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|                               Android OS Layer                                |
|  JobSchedulerService / AlarmManager / Battery Saver / Doze Engine             |
|  -> Mengevaluasi Hardware Constraints (Network, Charging, Idle, Battery)       |
+---------------------------------------+---------------------------------------+
                                        | Trigger Execution
+---------------------------------------v---------------------------------------+
|                       Worker Execution Subsystem                              |
|  SystemJobService -> WorkerWrapper -> WorkerFactory -> Custom CoroutineWorker  |
|  -> doWork() dieksekusi di background thread -> Output disimpan ke WorkDB     |
+-------------------------------------------------------------------------------+
```

#### Komponen Internal Utama:
1. **`WorkDatabase`**: Basis data Room internal yang terisolasi. Menyimpan seluruh spesifikasi `WorkSpec`, relasi antar-pekerjaan, tag, batasan perangkat (*constraints*), dan state eksekusi.
2. **`Schedulers` Engine**:
   - **`GreedyScheduler`**: Bekerja di dalam proses aktif untuk mengeksekusi pekerjaan secara instan tanpa menunggu overhead OS scheduler jika *constraints* terpenuhi.
   - **`SystemJobScheduler`**: Mendaftarkan pekerjaan ke `android.app.job.JobScheduler` milik OS. OS yang akan membangunkan aplikasi saat batasan terpenuhi.
3. **`WorkerWrapper`**: Kelas internal yang mengimplementasikan `Runnable`. Bertanggung jawab memuat metadata dari `WorkDatabase`, memvalidasi prasyarat eksekusi, memanggil instance `ListenableWorker`, dan menulis kembali status (`SUCCEEDED`, `FAILED`, `RETRY`) dalam satu transaksi ACID.
4. **Alokasi Sumber Daya & Doze Mode**:
   Saat OS memasuki mode *Doze*, akses jaringan dimatikan dan *wake lock* diabaikan. WorkManager menghormati jendela pemeliharaan (*maintenance windows*) OS, menunda pekerjaan non-kritis secara deterministik, kecuali pekerjaan ditandai sebagai *Expedited Work*.

---

### 4. Why & What

| Dimensi | WorkManager | Coroutines GlobalScope / Service | JobScheduler / AlarmManager |
| :--- | :--- | :--- | :--- |
| **Jaminan Eksekusi** | **Guaranteed**: Bertahan dari app kill, crash, dan OS reboot. | **Epimeral**: Terhenti seketika saat proses OS dihentikan (*OOM kill*). | **Guaranteed** (tetapi rentan diskrepansi implementasi antar OEM/API). |
| **Battery Optimization** | Terintegrasi native dengan *App Standby Buckets* dan *Doze Mode*. | Tidak efisien; rawan memicu *battery drain* dan *wake lock leakage*. | Memerlukan kalkulasi manual untuk Doze window. |
| **Abstraksi Multi-API** | Menyatukan logic untuk API 14 s/d 34+ di bawah satu interface. | Terbatas pada runtime aplikasi yang hidup. | Membutuhkan percabangan kode manual (`Build.VERSION.SDK_INT`). |
| **Konkurensi & Aliran Data** | Mendukung dependency graph (DAG), Chaining, dan Merger. | Memerlukan implementasi orkestrasi manual. | Sangat rumit untuk mengorkestrasi pipeline multi-step. |

**Kapan Menggunakan WorkManager?**
- Sinkronisasi data offline-first ke cloud (e.g., sinkronisasi keranjang belanja, mutasi audit log).
- Pemrosesan berkas berat yang dapat ditunda (*deferrable*): enkripsi file, kompresi video, backup database.
- Eksekusi analitik berkala dengan batasan jaringan *unmetered* dan kondisi pengisian daya.

**Kapan TIDAK Menggunakan WorkManager?**
- Perhitungan instan yang hasilnya dibutuhkan segera di UI (Gunakan *Coroutine* biasa dengan lifecycle scope UI).
- Streaming audio, pelacakan navigasi GPS turn-by-turn langsung (Gunakan native *Foreground Service* dengan `MediaSession` atau `LocationCallback`).

---

### 5. How (Workflow Detail)

Alur hidup deklarasi hingga eksekusi WorkManager di tingkat produksi:

```
[Definisikan Worker via AssistedInject]
                  |
[Bangun Constraints & WorkRequest (Backoff, Exponential Policy)]
                  |
[Enqueue ke WorkManager Instance]
                  |
       (Transkasi ACID di Room WorkDatabase)
                  |
       +----------+----------+
       | Terpenuhi           | Menunggu
[GreedyScheduler]     [SystemJobScheduler mendaftarkan ke OS]
       |                     |
       |               (Kondisi OS Terpenuhi: Unmetered + Charging)
       +--------->+<---------+
                  |
     [WorkerFactory Membuat Instance Worker]
                  |
     [doWork() -> Eksekusi Task Asinkron]
                  |
         +--------+--------+
         |                 |
     [Result.success()]  [Result.retry()]
         |                 |
  (State: SUCCEEDED)  (Hitung Backoff Delay -> Enqueue Ulang)
```

1. **Inisialisasi Khusus**: Nonaktifkan `WorkManagerInitializer` default di `AndroidManifest.xml` agar dependency injection (Hilt) dapat mengendalikan pembuatan worker.
2. **Assisted Injection Setup**: Buat worker turunan `CoroutineWorker` menggunakan anotasi `@HiltWorker` dan `@AssistedInject`.
3. **Konstruksi Request**:
   - Definisikan batasan (`NetworkType.UNMETERED`, `setRequiresCharging(true)`).
   - Tetapkan `BackoffPolicy.EXPONENTIAL` guna mencegah pembebanan server saat terjadi kegagalan jaringan (*thundering herd problem*).
4. **Enqueuing & Chaining**: Gunakan `.beginWith()`, `.then()`, dan `enqueue()`.
5. **Observasi Status**: Pantau status dan *progress updates* berbasis `Flow` menggunakan `getWorkInfoByIdFlow()`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Operasional
Bayangkan WorkManager sebagai **Sistem Ekspedisi Kargo Logistik Internasional**:
- **WorkRequest**: Surat jalan pengiriman paket yang berisi detail muatan dan prasyarat khusus (misal: "Kirim hanya jika truk pendingin aktif dan rute bebas hambatan").
- **WorkDatabase**: Buku manifes gudang pusat. Jika gudang mati lampu (aplikasi *force close*), catatan manifes tidak hilang.
- **Constraints**: Kebijakan bea cukai dan cuaca. Paket tidak diberangkatkan sebelum kondisi cuaca cerah (ada koneksi Wi-Fi).
- **WorkerFactory**: Manajer logistik yang mempekerjakan sopir berlisensi dan melengkapinya dengan peralatan navigasi (Dependency Injection).

#### Diagram Dependensi Pipeline (DAG):

```
       [FetchRemoteDeltaWorker]          [ValidateLocalSessionWorker]
                 \                                    /
                  \                                  /
                   v                                v
                 [MergeAndDecryptPayloadWorker (InputMerger)]
                                    |
                                    v
                        [CommitToRoomStorageWorker]
                                    |
                                    v
                        [TriggerAnalyticsWorker]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Basic CoroutineWorker dengan Constraints
Pekerjaan sederhana untuk membersihkan berkas *cache* sementara yang kedaluwarsa.

```kotlin
package com.enterprise.app.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

class SimpleCacheCleanupWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        return@withContext try {
            val cacheDirectory = applicationContext.cacheDir
            val deletedCount = cacheDirectory.listFiles()
                ?.filter { file -> System.currentTimeMillis() - file.lastModified() > MAX_CACHE_AGE_MS }
                ?.onEach(File::delete)
                ?.size ?: 0

            Result.success()
        } catch (throwable: Throwable) {
            Result.failure()
        }
    }

    companion object {
        private const val MAX_CACHE_AGE_MS = 24 * 60 * 60 * 1000L // 24 Jam
    }
}
```

#### 7.2 Practical Example (Production-Ready Architecture)
Pipeline sinkronisasi data transaksi keuangan offline:
1. `HiltWorker` terinjeksi dependency domain layer.
2. Penanganan limit payload 10KB menggunakan disk-caching token pointer.
3. Dukungan *Expedited Work* dan *Foreground Service* untuk sistem operasi API 31+.

```kotlin
// 1. Injeksi Worker Menggunakan Hilt
package com.enterprise.app.work

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.enterprise.app.R
import com.enterprise.app.domain.repository.TransactionRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException

@HiltWorker
class TransactionSyncWorker @AssistedInject constructor(
    @Assisted private val context: Context,
    @Assisted private val params: WorkerParameters,
    private val transactionRepository: TransactionRepository
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        // Ambil transaction batch pointer (bukan raw data, hindari limit 10KB)
        val batchPointerId = inputData.getString(KEY_BATCH_POINTER_ID)
            ?: return@withContext Result.failure(
                workDataOf(KEY_ERROR_REASON to "BATCH_POINTER_MISSING")
            )

        // Elevasi ke Foreground Service jika berjalan sebagai Expedited Work
        if (runAttemptCount == 0 && isForegroundWorkSupported()) {
            try {
                setForeground(createForegroundInfo(batchPointerId))
            } catch (e: Exception) {
                // Tangani ForegroundServiceStartNotAllowedException secara graceful
            }
        }

        return@withContext try {
            // Update initial progress
            setProgress(workDataOf(KEY_PROGRESS to 10))

            // Eksekusi Sinkronisasi Domain
            val syncedCount = transactionRepository.syncPendingTransactions(batchPointerId) { current, total ->
                val percentage = ((current.toFloat() / total.toFloat()) * 100).toInt()
                setProgressAsync(workDataOf(KEY_PROGRESS to percentage))
            }

            val outputData = workDataOf(
                KEY_SYNCED_COUNT to syncedCount,
                KEY_BATCH_POINTER_ID to batchPointerId
            )
            Result.success(outputData)
        } catch (ioException: IOException) {
            if (runAttemptCount < MAX_RETRIES) {
                Result.retry()
            } else {
                Result.failure(workDataOf(KEY_ERROR_REASON to "MAX_RETRIES_EXCEEDED"))
            }
        } catch (domainException: Exception) {
            Result.failure(workDataOf(KEY_ERROR_REASON to (domainException.message ?: "UNKNOWN_ERROR")))
        }
    }

    private fun isForegroundWorkSupported(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O

    private fun createForegroundInfo(batchId: String): ForegroundInfo {
        createNotificationChannel()

        val notification: Notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle("Sinkronisasi Transaksi Finansial")
            .setContentText("Memproses batch: $batchId")
            .setSmallIcon(R.drawable.ic_sync)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            ForegroundInfo(NOTIFICATION_ID, notification)
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Sinkronisasi Background",
                NotificationManager.IMPORTANCE_LOW
            )
            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    companion object {
        const val KEY_BATCH_POINTER_ID = "KEY_BATCH_POINTER_ID"
        const val KEY_PROGRESS = "KEY_PROGRESS"
        const val KEY_SYNCED_COUNT = "KEY_SYNCED_COUNT"
        const val KEY_ERROR_REASON = "KEY_ERROR_REASON"
        private const val CHANNEL_ID = "sync_channel_id"
        private const val NOTIFICATION_ID = 4091
        private const val MAX_RETRIES = 5
    }
}
```

```kotlin
// 2. Custom Application Provider untuk WorkManager
package com.enterprise.app

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class EnterpriseApplication : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .setMinimumLoggingLevel(android.util.Log.INFO)
            .build()
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Aplikasi *Point of Sale* (POS) untuk jaringan ritel dengan 10.000+ toko. Kasir bekerja secara offline ketika konektivitas terputus, menghasilkan ribuan transaksi tersimpan di Room DB. Saat koneksi kembali, ribuan data transaksi harus diunggah tanpa menyebabkan duplikasi pemotongan saldo atau kehabisan memori (*OOM*).

#### Solusi Arsitektur:
1. **Idempotency Execution Key**: Setiap request sinkronisasi dibekali UUID unik yang disimpan di basis data transaksi lokal (`idempotency_key`). Backend menggunakan kunci ini untuk *deduplication*.
2. **Batched Payload Delegation**: Alih-alih memasukkan 500 transaksi ke dalam `androidx.work.Data` (yang melanggar batas 10KB), transaksi dikelompokkan ke dalam satu tabel batch Room (`SyncBatchEntity`). `WorkRequest` hanya membawa `batch_id`.
3. **Execution Pipeline**:
   - `CreateBatchWorker`: Memvalidasi transaksi pending, menyegel batch, mengunci baris di Room DB.
   - `UploadBatchWorker`: Mengunggah batch dengan *exponential backoff*.
   - `PurgeSyncedDataWorker`: Menghapus transaksi yang berhasil diverifikasi dari penyimpanan lokal.

```kotlin
package com.enterprise.app.orchestration

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import java.util.concurrent.TimeUnit

class SyncCoordinator(private val context: Context) {

    fun triggerResilientSync(batchId: String) {
        val networkConstraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .setRequiresBatteryNotLow(true)
            .build()

        val uploadWorkRequest = OneTimeWorkRequestBuilder<TransactionSyncWorker>()
            .setConstraints(networkConstraints)
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                OneTimeWorkRequestBuilder<TransactionSyncWorker>().defaultBackoffDelayMillis,
                TimeUnit.MILLISECONDS
            )
            .setInputData(workDataOf(TransactionSyncWorker.KEY_BATCH_POINTER_ID to batchId))
            .addTag(TAG_TRANSACTION_SYNC)
            .build()

        WorkManager.getInstance(context)
            .enqueueUniqueWork(
                "sync_batch_$batchId",
                androidx.work.ExistingWorkPolicy.KEEP,
                uploadWorkRequest
            )
    }

    companion object {
        const val TAG_TRANSACTION_SYNC = "sync:transaction"
    }
}
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- |
| **Expedited Jobs (`setExpedited`)** | Dijalankan secepat mungkin oleh OS tanpa penundaan standard Doze. | Kuota eksekusi dibatasi oleh OS. Jika habis, dapat melempar `OutOfQuotaException` kecuali fallback disiapkan. |
| **PeriodicWorkRequest** | Eksekusi otomatis terjadwal secara berkala dengan overhead konfigurasi minimal. | Interval minimum terkunci di 15 menit. Waktu eksekusi tidak presisi; tergantung algoritma optimasi baterai OS. |
| **Data Payload (10KB Limit)** | Serialisasi data cepat via SQLite internal. | Terbatas 10,240 byte. Jika dilanggar memicu `IllegalStateException` fatal yang menghentikan aplikasi. |
| **ForegroundInfo Integration** | Mencegah OS mematikan worker saat proses berat berlangsung. | Mengharuskan penayangan notifikasi persisten kepada pengguna; wajib deklarasi `android:foregroundServiceType` di API 34+. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Pelanggaran Batas Payload Data (`IllegalStateException: Data cannot exceed 10240 bytes`)
- **Akar Masalah**: Memasukkan file biner (byte array), base64 gambar, atau JSON berukuran besar langsung ke objek `Data`.
- **Solusi**: Terapkan pola *Token Passing*. Simpan data ke berkas cache terenkripsi atau tabel database Room, lalu kirim *Path URI* atau *UUID Primary Key* melalui `Data`.

#### 2. Crash `ForegroundServiceStartNotAllowedException` (Android 12+)
- **Akar Masalah**: Memanggil `setForegroundAsync()` dari worker saat aplikasi berada di background dan tidak memenuhi izin pengecualian OS.
- **Solusi**: Gunakan `OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST` pada `setExpedited()` atau tangani pengecualian secara defensif dalam blok `try-catch`.

#### 3. Custom WorkerFactory Tidak Terdaftar (Instansiasi Reflection Gagal)
- **Akar Masalah**: Masih menggunakan default AndroidX Startup Initializer sementara HiltWorker digunakan, menyebabkan `NoSuchMethodException` saat OS mencoba memanggil konstruktor bawaan.
- **Solusi**: Nonaktifkan `androidx.startup` untuk WorkManager di `AndroidManifest.xml`:

```xml
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
```

#### 4. Silent Cancellation via Coroutine Failure
- **Akar Masalah**: Menangkap semua `Exception` menggunakan `catch (e: Exception)` generik sehingga `CancellationException` ikut tertangkap, memutus siklus pembatalan alami Coroutine.
- **Solusi**: Jangan pernah menelan `CancellationException` tanpa melemparnya kembali (`rethrow`), atau tangani tipe exception secara spesifik (misal: `IOException`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Disable Default Initializer**: Pastikan `androidx.work.WorkManagerInitializer` dihapus dari manifest dan `Configuration.Provider` diimplementasikan secara eksplisit di `Application`.
- [ ] **Strict 10KB Constraint Compliance**: Tidak pernah memasukkan payload mentah ke `androidx.work.Data`. Gunakan mekanisme Room DB pointer atau Local File Storage.
- [ ] **Exponential Backoff**: Selalu tentukan backoff policy eksplisit untuk operasi jaringan (`BackoffPolicy.EXPONENTIAL`).
- [ ] **Unique Work Policy**: Tentukan strategi penanganan duplikasi (`ExistingWorkPolicy.KEEP` atau `REPLACE` atau `APPEND_OR_REPLACE`).
- [ ] **Foreground Service Types (API 34)**: Deklarasikan atribut `android:foregroundServiceType` yang sesuai di tag `<service>` manifest untuk `SystemForegroundService`.
- [ ] **Idempotent Workers**: Pastikan kode `doWork()` aman dieksekusi berulang kali tanpa merusak state bisnis jika worker terbunuh di tengah jalan.
- [ ] **ProGuard/R8 Rules**: Tambahkan aturan proteksi *reflection* untuk implementasi worker kustom:
  ```proguard
  -keepclasseswithmembers class * extends androidx.work.Worker {
      public <init>(android.content.Context, androidx.work.WorkerParameters);
  }
  -keepclasseswithmembers class * extends androidx.work.ListenableWorker {
      public <init>(android.content.Context, androidx.work.WorkerParameters);
  }
  ```

---

### 12. Hands-on Practice
Simpan seluruh latihan pada direktori: `hands-on/m02/`

#### Langkah 1: Setup WorkManager Test Driver & Dependency
Tambahkan dependensi pada file `hands-on/m02/build.gradle.kts`:
```kotlin
dependencies {
    implementation("androidx.work:work-runtime-ktx:2.9.0")
    implementation("androidx.hilt:hilt-work:1.2.0")
    kapt("androidx.hilt:hilt-compiler:1.2.0")
    testImplementation("androidx.work:work-testing:2.9.0")
}
```

#### Langkah 2: Buat Resilient Data Purge Worker
Buat file `hands-on/m02/src/main/java/com/enterprise/app/LogPurgeWorker.kt`:
```kotlin
package com.enterprise.app

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class LogPurgeWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val retentionDays = inputData.getInt(KEY_RETENTION_DAYS, -1)
        if (retentionDays <= 0) {
            return@withContext Result.failure(workDataOf(KEY_RESULT to "INVALID_RETENTION_DAYS"))
        }

        // Simulasi Purge Operasi
        val recordsDeleted = 1500
        Result.success(workDataOf(KEY_RECORDS_PURGED to recordsDeleted))
    }

    companion object {
        const val KEY_RETENTION_DAYS = "RETENTION_DAYS"
        const val KEY_RECORDS_PURGED = "RECORDS_PURGED"
        const val KEY_RESULT = "RESULT"
    }
}
```

#### Langkah 3: Implementasi Integrasi Unit Test WorkManager
Buat file `hands-on/m02/src/test/java/com/enterprise/app/LogPurgeWorkerTest.kt`:
```kotlin
package com.enterprise.app

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker
import androidx.work.testing.TestListenableWorkerBuilder
import androidx.work.workDataOf
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class LogPurgeWorkerTest {

    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
    }

    @Test
    fun testLogPurgeWorker_whenRetentionDaysInvalid_returnsFailure() = runBlocking {
        val worker = TestListenableWorkerBuilder<LogPurgeWorker>(context)
            .setInputData(workDataOf(LogPurgeWorker.KEY_RETENTION_DAYS to -1))
            .build()

        val result = worker.doWork()

        assertTrue(result is ListenableWorker.Result.Failure)
    }

    @Test
    fun testLogPurgeWorker_whenValid_returnsSuccessWithDeletedCount() = runBlocking {
        val worker = TestListenableWorkerBuilder<LogPurgeWorker>(context)
            .setInputData(workDataOf(LogPurgeWorker.KEY_RETENTION_DAYS to 30))
            .build()

        val result = worker.doWork()

        assertTrue(result is ListenableWorker.Result.Success)
        val successResult = result as ListenableWorker.Result.Success
        assertEquals(1500, successResult.outputData.getInt(LogPurgeWorker.KEY_RECORDS_PURGED, 0))
    }
}
```

---

### 13. Exercise

#### Level: Easy
Konfigurasikan sebuah `PeriodicWorkRequest` bernama `TelemetryHeartbeatWorker` yang dijalankan setiap 4 jam, hanya saat perangkat terhubung ke Wi-Fi (`NetworkType.UNMETERED`) dan baterai tidak lemah.

#### Level: Medium
Rancang pipeline pengolahan gambar menggunakan WorkManager Chaining:
1. `DownloadImageWorker`: Mengunduh berkas gambar mentah dari server dan menyimpannya ke storage privat internal.
2. `CompressAndWatermarkWorker`: Membaca berkas hasil download, melakukan kompresi 50%, menambahkan watermark, dan menyimpannya kembali.
3. `UploadImageWorker`: Mengunggah gambar yang telah dikompresi ke CDN internal.
Setiap worker harus saling bertukar path absolut berkas melalui `workDataOf()` tanpa melebihi batas 10KB.

#### Level: Hard
Bangun worker kustom yang mengimplementasikan `ForegroundInfo` dengan tipe `FOREGROUND_SERVICE_TYPE_DATA_SYNC` yang mendukung graceful degradation saat berjalan pada kondisi *low memory* dan memantau status upload ribuan baris data transaksi offline. Jika proses dihentikan oleh OS (karena constraint baterai berubah), worker harus mampu melanjutkan upload (*resumable sync*) dari baris index terakhir tanpa mengulang dari awal saat OS membangunkannya kembali.

---

### 14. Challenge

**Studi Kasus Enterprise**:
Sebuah platform perbankan digital berskala nasional membutuhkan modul sinkronisasi dokumen e-KYC (berisi foto KTP, rekaman liveness video pendek, dan data biometrik terenkripsi) yang diunggah dari area dengan kualitas sinyal buruk (rural areas).

**Spesifikasi Persyaratan**:
1. Seluruh payload berukuran total hingga 25 MB per pendaftaran.
2. Sistem harus mengeksekusi pipeline dengan urutan: Validasi Hash Integritas -> Enkripsi AES-GCM 256 Lokal -> Kompresi Chunk -> Multi-part Chunks Parallel Upload -> Finalisasi Session API.
3. Sistem **wajib tahan banting**: Jika baterai perangkat drop di bawah 15% atau koneksi internet mati di tengah proses multi-part upload, proses harus ditangguhkan dan melanjutkan chunk upload yang tersisa secara deterministik saat kondisi normal kembali (tidak boleh mengunggah ulang chunk yang sudah selesai).
4. Sesuai regulasi data privasi perbankan, batasan payload `Data` tidak boleh dilanggar, berkas temporer wajib di-shred/delete setelah sukses, dan *audit trace token* harus dipublikasikan ke konsol analitik secara aman.

**Tugas Anda**: Rancang spesifikasi arsitektur kelas, skema data Room pendukung, alur dependency injection menggunakan Hilt, dan skema DAG (Directed Acyclic Graph) chaining request untuk WorkManager. Tuliskan implementasi inti worker orchestration pipeline secara lengkap.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa batasan ukuran maksimum objek `androidx.work.Data` yang dapat dipertukarkan antar `WorkRequest`?
   - A. 1 MB
   - B. 512 KB
   - C. 10.240 byte (10 KB)
   - D. Tidak terbatas selama memori RAM mencukupi
2. Berapa interval minimum yang diizinkan untuk penjadwalan `PeriodicWorkRequest` pada WorkManager?
   - A. 5 Menit
   - B. 15 Menit
   - C. 30 Menit
   - D. 1 Jam
3. Apa perbedaan mendasar antara `Result.failure()` dan `Result.retry()`?
   - A. `Result.retry()` langsung menghentikan worker secara permanen.
   - B. `Result.retry()` memasukkan kembali worker ke antrean penjadwalan sesuai kebijakan backoff, sedangkan `Result.failure()` menandai status akhir pekerjaan sebagai gagal permanen.
   - C. `Result.failure()` memicu crash runtime aplikasi.
   - D. `Result.retry()` hanya bisa dipanggil satu kali dalam lifecycle worker.
4. Apa peran dari anotasi `@HiltWorker` pada Worker class?
   - A. Menjadikan worker berjalan otomatis di Main Thread.
   - B. Mengintegrasikan instansiasi worker ke dalam DI graph Hilt menggunakan Assisted Injection.
   - C. Menyimpan state worker secara otomatis ke Firebase.
   - D. Mengubah worker menjadi Foreground Service native.
5. Bagaimana cara WorkManager mempertahankan penjadwalan pekerjaan ketika perangkat dimatikan (*reboot*)?
   - A. Disimpan dalam SharedPreferences.
   - B. Mengandalkan RAM perangkat yang dipertahankan menggunakan low power mode.
   - C. Menggunakan SQLite Room DB internal yang otomatis mendaftarkan ulang pekerjaan ke OS saat menerima broadcast `BOOT_COMPLETED`.
   - D. WorkManager tidak dapat bertahan dari kondisi reboot.

#### 5 Pertanyaan Intermediate
6. Mengapa pengembang harus menghapus default `WorkManagerInitializer` jika menggunakan custom `WorkerFactory` via Hilt?
   - A. Supaya memori heap tidak mengalami leak.
   - B. Karena default initializer menggunakan refleksi konstruktor default yang akan melempar exception saat worker membutuhkan injeksi dependency via runtime factory.
   - C. Karena Android OS melarang penggunaan initializer default di atas Android 10.
   - D. Untuk mempercepat waktu kompilasi gradle.
7. Apa tujuan utama dari fitur *Expedited Work* yang diperkenalkan pada API modern?
   - A. Mengabaikan semua izin keamanan Android.
   - B. Memberikan slot eksekusi mendesak dengan latensi minimal tanpa terhambat penundaan normal Doze Mode, memanfaatkan kuota khusus yang diberikan OS.
   - C. Menghapus kebutuhan deklarasi `CoroutineWorker`.
   - D. Mengizinkan pengunggahan payload tanpa batasan kuota internet pengguna.
8. Jika sebuah worker sedang berjalan dan OS memutuskan untuk menghentikannya (misalnya karena constraint konektivitas hilang), mekanisme apa yang terjadi di `CoroutineWorker`?
   - A. Proses worker di-kill seketika melalui sinyal `SIGKILL`.
   - B. Coroutine worker dibatalkan via cooperative cancellation (`CancellationException`), dan method `onStopped()` dipanggil.
   - C. WorkManager melempar fatal exception ke thread UI.
   - D. Worker terus berjalan di background sampai proses selesai secara paksa.
9. Manakah pernyataan yang BENAR mengenai penggunaan `ExistingWorkPolicy.KEEP`?
   - A. Jika pekerjaan dengan nama unik yang sama sudah ada dan belum selesai, request baru akan diabaikan.
   - B. Request baru akan menggantikan pekerjaan lama secara paksa.
   - C. Request baru akan digabungkan secara paralel.
   - D. Pekerjaan lama akan dibatalkan seketika dan masuk ke antrean retry.
10. Pada Android 14 (API 34), apa konsekuensinya jika Anda menjalankan long-running worker dengan `setForegroundAsync()` tanpa mendeklarasikan `android:foregroundServiceType` pada manifes?
    - A. Notifikasi tidak bersuara.
    - B. Sistem melempar crash runtime `MissingForegroundServiceTypeException`.
    - C. Worker berjalan seperti biasa tanpa perubahan.
    - D. Sistem secara otomatis memilih tipe `mediaPlayback`.

#### 3 Skenario Kasus Produksi
11. **Skenario Kasus 1**: Tim Anda merilis fitur ekspor laporan audit finansial terenkripsi menggunakan WorkManager. Namun, beberapa user dengan ponsel vendor tertentu (OEM agresif seperti Xiaomi/MIUI atau Samsung/OneUI) melaporkan bahwa ekspor tidak pernah berjalan jika aplikasi ditutup dari Recent Apps list. Apa root cause arsitekturalnya dan langkah mitigasinya?
12. **Skenario Kasus 2**: Sebuah pipeline pemrosesan analitik menggunakan chain: Worker A -> Worker B -> Worker C. Worker B mengalami `Result.retry()` karena kegagalan jaringan sementara. Bagaimana status dan lifecycle Worker C selama Worker B berada dalam masa backoff retry?
13. **Skenario Kasus 3**: Terjadi error `TransactionTooLargeException` atau `IllegalStateException: Data cannot exceed 10240 bytes` saat Worker pengunggah video mencoba mengirim metadata frame array ke Worker pengunggah analitik. Rancang refactoring arsitektur untuk mengatasi masalah tersebut tanpa kehilangan integritas data!

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Jawaban Pertanyaan Basic
1. **C** - Batasan kapasitas objek `Data` adalah 10.240 byte (10 KB). Melebihi batasan ini akan melempar runtime exception.
2. **B** - Interval periodik terkecil yang diizinkan oleh sistem adalah 15 menit (`PeriodicWorkRequest.MIN_PERIODIC_INTERVAL_MILLIS`).
3. **B** - `Result.retry()` memicu kalkulasi ulang waktu penjadwalan via backoff criteria, sedangkan `Result.failure()` adalah status terminal kegagalan.
4. **B** - `@HiltWorker` bersama `@AssistedInject` mengizinkan pembuatan worker dengan dependensi domain yang di-resolve oleh injector Hilt.
5. **C** - WorkManager mengandalkan Room DB internal untuk persistensi dan mendaftarkan broadcast receiver `ACTION_BOOT_COMPLETED` guna memulihkan antrean pekerjaan ke OS Scheduler.

#### Jawaban Pertanyaan Intermediate
6. **B** - Inisialisasi default berusaha menginstansiasi worker via reflection konstruktor standar `(Context, WorkerParameters)`. Worker dengan injeksi Hilt memerlukan parameter dependensi tambahan, sehingga akan crash jika factory kustom belum didaftarkan.
7. **B** - Expedited Work ditujukan untuk pekerjaan mendesak yang memerlukan eksekusi segera dengan mengecualikan batasan Doze standard, diatur melalui kuota OS.
8. **B** - WorkManager CoroutineWorker mengimplementasikan Structured Concurrency: pembatalan tugas dilakukan dengan membatalkan CoroutineScope worker melalui `CancellationException`.
9. **A** - `ExistingWorkPolicy.KEEP` mempertahankan pekerjaan yang pertama kali didaftarkan dan menolak (mengabaikan) request baru jika request lama belum mencapai status terminal.
10. **B** - Android 14 mewajibkan secara ketat deklarasi foreground service type di manifest dan saat memanggil foreground info, ketiadaannya memicu runtime crash.

#### Pembahasan Skenario Kasus Produksi
11. **Skenario 1**:
    - *Root Cause*: Sebagian OEM memiliki vendor-specific task killer yang agresif (membunuh proses secara permanen dan menolak wake up intent dari `JobScheduler` saat aplikasi di-*swipe* dari app switch).
    - *Mitigasi*:
      1. Terapkan *Expedited Work* untuk task penting.
      2. Edukasi pengguna melalui UI khusus untuk menonaktifkan "Battery Optimization" (*Battery Saver Whitelist*) via intent `Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`.
      3. Pastikan pekerjaan memiliki *Constraints* realistis yang tidak memblokir eksekusi terus-menerus.
12. **Skenario 2**:
    - Status Worker C tetap berada pada state `BLOCKED`. Worker C tidak akan pernah dieksekusi atau dipanggil sebelum Worker B mencapai status terminal `Result.success()`. Jika Worker B pada akhirnya menghabiskan batas retry dan menghasilkan `Result.failure()`, maka Worker C akan otomatis ditandai sebagai `FAILED` tanpa pernah dieksekusi.
13. **Skenario 3**:
    - *Refactoring*: Hapus seluruh array byte/frame dari objek `Data`.
    - Simpan metadata frame mentah ke dalam Room Database lokal atau tulis ke berkas temporer biner di internal private storage (`context.filesDir/frames/`).
    - Kirimkan hanya URI berkas atau Primary Key DB ID (String UUID) melalui `workDataOf(KEY_FRAME_PAYLOAD_REF to recordUuid)`.
    - Worker target membaca data langsung dari database lokal/storage berdasarkan ID/URI tersebut.

---

### 16. Summary

1. **Guaranteed vs Ephemeral**: WorkManager dirancang untuk *guaranteed background execution* yang tahan terhadap penghentian aplikasi dan restart OS, bukan untuk eksekusi real-time berbasis UI.
2. **Kepatuhan Batasan Sistem**: Android modern (API 26-34+) sangat membatasi background execution. WorkManager beroperasi selaras dengan *Doze Mode*, *App Standby Buckets*, dan *Foreground Service Restrictions*.
3. **Payload Architecture (Pointer Over Data)**: Kapasitas objek `Data` dibatasi sebesar 10KB. Pola arsitektur enterprise selalu menggunakan *Token/Pointer Passing* yang memisahkan pengiriman sinyal status dengan penyimpanan data aktual (Room DB/Internal Storage).
4. **Idempotency & Clean Retry**: Mengingat worker dapat dijalankan ulang oleh OS saat kondisi lingkungan berubah, logika bisnis di dalam `doWork()` wajib bersifat idempotent guna mencegah data duplikat atau status korup di level database dan server.