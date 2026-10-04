# BAB 07: Quiz, Challenge, & Knowledge Check
**Asynchronous Background Processing & WorkManager**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dilema Arsitektur Background Processing:**
   Jelaskan perbedaan fundamental dalam model eksekusi antara in-memory asynchronous processing (Kotlin Coroutines yang terikat pada `ViewModelScope` atau `ProcessLifecycleOwner`), `Foreground Service`, dan `WorkManager`. Mengapa mengandalkan Coroutine global (`GlobalScope` atau scope custom) untuk operasi kritis seperti sinkronisasi database offline-to-remote adalah anti-pattern yang berbahaya di platform Android modern?

2. **Dampak Doze Mode dan App Standby Buckets:**
   Bagaimana sistem operasi Android (sejak Marshmallow dan Pie) memperlakukan background tasks melalui *Doze Mode* dan *App Standby Buckets*? Terangkan bagaimana `WorkManager` beradaptasi dengan *maintenance windows* dan mengapa eksekusi tugasnya bersifat *deferrable* (dapat ditunda) secara by-design.

3. **Anatomi dan Evaluasi Constraints:**
   Sebutkan dan analisis cara kerja internal `Constraints` pada WorkManager (seperti `NetworkType.UNMETERED`, `RequiresBatteryNotLow`, dan `RequiresDeviceIdle`). Apa yang terjadi pada level OS ketika sebuah constraint yang sebelumnya terpenuhi tiba-tiba hilang (misalnya pengguna berpindah dari Wi-Fi ke data seluler berbayar) di tengah-tengah eksekusi `Worker`?

4. **Prinsip Idempotensi dalam Background Tasks:**
   Mengapa *idempotensi* (idempotency) menjadi prasyarat mutlak ketika Anda mendesain logika di dalam `doWork()` pada `CoroutineWorker`? Kaitkan jawaban Anda dengan terminasi proses secara mendadak oleh Low Memory Killer (LMK) dan jaminan *at-least-once execution* dari WorkManager.

5. **PeriodicWorkRequest vs Exact AlarmManager:**
   Bandingkan batasan arsitektur antara `PeriodicWorkRequest` dan `AlarmManager.setExactAndAllowWhileIdle()`. Mengapa Android memberlakukan interval minimum 15 menit dengan *flex interval* pada `PeriodicWorkRequest`, dan skenario sistem apa yang sah menggunakan `AlarmManager` presisi tinggi dibandingkan `WorkManager`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Persistensi dan Abstraksi Sub-sistem:**
   Bedah arsitektur internal WorkManager ketika sebuah `WorkRequest` di-*enqueue*. Bagaimana interaksi antara `WorkManagerImpl`, basis data internal Room (`workmanager.db`), dan framework-level scheduler (`JobScheduler` pada API 23+, atau fallback `AlarmManager` + `BroadcastReceiver` pada perangkat lawas)? Apa implikasi performa I/O jika aplikasi melakukan enqueue puluhan worker secara simultan tanpa chaining?

2. **Kooperatif Threading dan Pembatalan pada CoroutineWorker:**
   Bagaimana `CoroutineWorker` menerjemahkan sinyal terminasi dari OS ke dalam pembatalan coroutine? Jika sebuah thread native atau operasi I/O blocking (seperti `InputStream.read()`) dijalankan di dalam `doWork()`, mengapa pembatalan worker bisa gagal menyebabkan worker berstatus zombie/stuck, dan bagaimana cara memitigasinya secara defensif?

3. **Expedited Jobs vs Foreground Service Limits (Android 12+):**
   Mulai Android 12 (API 31), pembatasan ketat diterapkan untuk memulai Foreground Service dari background. Jelaskan mekanisme kerja *Expedited Work* (`setExpedited()`) pada WorkManager. Bagaimana WorkManager mengelola kuota eksekusi (*Execution Quota*), apa peran `OutOfQuotaPolicy`, dan bagaimana fallback ke regular work diatur di bawah kap mesin?

4. **Resolusi Konflik Unique Work:**
   Analisis state machine WorkManager saat mengeksekusi `enqueueUniqueWork` atau `enqueueUniquePeriodicWork` menggunakan parameter:
   * `ExistingWorkPolicy.REPLACE`
   * `ExistingWorkPolicy.KEEP`
   * `ExistingWorkPolicy.APPEND_OR_REPLACE`
   
   Jelaskan race condition apa yang dapat terjadi pada data lokal jika worker lama berstatus `RUNNING` saat kebijakan `REPLACE` dieksekusi, serta bagaimana menangani *cancellation signal* di sisi database.

5. **Instrumentasi dan Debugging State Engine WorkManager:**
   Bagaimana metodologi Anda untuk mengisolasi kegagalan worker yang tidak kunjung dieksekusi di fase staging? Tunjukkan perintah CLI (`adb shell dumpsys jobscheduler`, `adb shell cmd statusbar`, atau `adb shell am make-uid-idle`) untuk memanipulasi constraints dan memvalidasi transisi state WorkManager tanpa menunggu siklus waktu alami.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Crash BadProvider / SQLite Full-Disk Exception pada Skala Masif
Sebuah aplikasi logistik enterprise dengan 500.000 active device mengalami crash cascade di level OS yang dilaporkan via Play Console: `SQLiteFullException` dan `IllegalStateException: WorkManager is already initialized`. Masalah ini terdeteksi setelah tim merilis fitur audit log yang meng-enqueue satu `OneTimeWorkRequest` untuk setiap kali kurir memindai barcode paket (rata-rata 2.000 scan per shift kerja).

* **Pertanyaan Diagnostik:**
  1. Mengapa pola pembuatan `OneTimeWorkRequest` granular per-event memicu degradasi fatal pada database internal Room milik WorkManager?
  2. Bagaimana Anda merestrukturisasi sistem background logging ini menggunakan teknik *batching/aggregation* dan *chaining* agar overhead I/O dan footprint storage terminimalisir?
  3. Mengapa exception inisialisasi WorkManager terjadi dan bagaimana implementasi `Configuration.Provider` secara on-demand dapat menyelesaikan masalah lifecycle inisialisasi tersebut?

---

### Skenario B: Race Condition dan Double-Debit pada Offline Sync Engine
Aplikasi Point-of-Sale (POS) kasir restoran dirancang beroperasi offline. Saat koneksi internet terputus, mutasi pembayaran disimpan di database Room lokal dan dijadwalkan untuk sinkronisasi menggunakan `CoroutineWorker` dengan `Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()`. Ketika internet kembali hidup tapi berada dalam kondisi *flaky* (sinyal edge dengan packet loss 80%), worker berhasil mengirimkan payload HTTP POST ke payment gateway, namun sebelum response HTTP 200 diterima dan dicatat di database lokal, OS mematikan worker karena timeout eksekusi (10 menit) atau fluktuasi network constraint. Ketika koneksi stabil 2 menit kemudian, WorkManager me-retry tugas tersebut, menyebabkan debit ganda pada rekening pelanggan.

* **Pertanyaan Diagnostik:**
  1. Di mana letak kegagalan rancangan transaksional antara client-side state machine dan backend API?
  2. Rancang strategi integrasi *Idempotency Key* (UUID v4) berbasis transaksi lokal dan skema dua-fase (*Pending -> In-Flight -> Committed*) untuk memastikan retry WorkManager tidak pernah memicu mutasi finansial duplikat.
  3. Bagaimana Anda memanfaatkan `ForegroundInfo` dan custom `BackoffPolicy` (Linear vs Exponential) untuk menangani timeout dan jaringan yang tidak stabil?

---

### Skenario C: Dilema Telemetri Real-Time vs Baterai pada Fleet Tracking
Sebuah perusahaan ride-hailing meminta Anda membangun modul pelacakan posisi driver. Tim produk menuntut agar koordinat GPS dikirimkan ke server setiap 10 detik saat driver aktif membawa penumpang, dan setiap 15 menit saat driver berstatus idle (menunggu order). Seorang Software Engineer junior mengusulkan penggunaan `WorkManager` untuk kedua skenario tersebut dengan alasan "menghemat baterai dan menyederhanakan kode".

* **Pertanyaan Diagnostik:**
  1. Mengapa usulan engineer junior tersebut cacat secara teknis dan mustahil memenuhi SLA pelacakan interval 10 detik menggunakan WorkManager murni?
  2. Arsitektur hibrida apa yang paling tepat untuk memisahkan kedua use case ini? (Evaluasi penggunaan bound/unbound `Foreground Service` dengan persistent notification + Location API vs `PeriodicWorkRequest`).
  3. Bagaimana transisi kepemilikan proses (handover) dilakukan saat status driver berubah dari *Idle* (WorkManager) menjadi *Active Trip* (Foreground Service), tanpa meninggalkan *gap tracking* maupun *memory leak*?

---

## 4. Chapter Challenge

### Tantangan Praktis: Resilient Offline-First Chunked Media Uploader Engine

#### Problem Statement
Aplikasi inspeksi infrastruktur sipil mewajibkan pengguna mengunggah video inspeksi berukuran besar (100MB – 500MB) dari area blank-spot pedalaman. Upload sering gagal di tengah jalan karena fluktuasi sinyal. Pengguna tidak boleh dipaksa membuka aplikasi selama proses upload berlangsung. Sistem harus mampu melanjutkan (*resume*) upload dari chunk terakhir yang berhasil, bukan mengulang dari 0%, serta membatasi dampak terhadap konsumsi baterai dan memori.

#### Requirements
1. **Pipeline Arsitektur WorkManager:**
   * Bangun mekanisme *Chained Work*:
     * **Worker 1 (MediaPreprocessorWorker):** Melakukan kompresi video, menghitung checksum SHA-256 berkas, dan memecah file video menjadi blok-blok biner kecil (chunks @ 2MB). Status chunk disimpan di Room database lokal (`MediaChunkEntity`).
     * **Worker 2 (ChunkedUploadWorker):** Mengunggah chunk secara sekuensial. Mendukung mekanisme resume: membaca chunk mana yang berstatus `PENDING`, mengunggahnya ke mock server API, dan memperbarui status chunk menjadi `UPLOADED`.
     * **Worker 3 (VerificationWorker):** Mengirimkan sinyal konsolidasi ke server untuk merakit chunk, memvalidasi checksum final, dan membersihkan chunk file sementara dari disk lokal (`cacheDir`).
2. **Constraints & Resilience:**
   * Wajib memberlakukan constraint: `NetworkType.CONNECTED` dan `RequiresBatteryNotLow`.
   * Implementasikan custom exponential backoff policy (mulai dari 15 detik hingga maksimal 1 jam).
   * Gunakan `CoroutineWorker` dan tangani `CancellationException` dengan benar untuk menyimpan index chunk terakhir yang sedang diunggah saat OS membatalkan task.
3. **User Visibility:**
   * Jadikan `ChunkedUploadWorker` berjalan sebagai *Expedited Work* (atau panggil `setForeground()` dengan `ForegroundInfo` pada Android < 12) untuk menampilkan progress notification persentase upload secara real-time.

#### Constraints Teknis
* **No Third-Party Work Libraries:** Dilarang menggunakan library wrapper pihak ketiga; murni gunakan `androidx.work:work-runtime-ktx`.
* **Zero Main-Thread Blocking:** Operasi read/write file I/O chunking dan hashing SHA-256 wajib berjalan di background thread yang tepat (`Dispatchers.IO`).
* **Memory Safety:** Dilarang me-load seluruh video 500MB ke dalam memori RAM (`byte[]`). Pembacaan file harus menggunakan streaming buffer (misalnya `FileInputStream` dengan buffer 8KB).

#### Expected Output
1. File implementasi:
   * `MediaUploadWorkManager.kt` (Orkestrasi enqueue unique work chain).
   * `MediaPreprocessorWorker.kt`, `ChunkedUploadWorker.kt`, `VerificationWorker.kt`.
   * Unit test menggunakan `WorkManagerTestInitHelper` yang membuktikan:
     * Alur rantai berjalan sukses hingga status `Enqueued` -> `Running` -> `Succeeded`.
     * Ketika constraint jaringan dimatikan di tengah-tengah `ChunkedUploadWorker`, state tersimpan aman dan proses dapat melanjutkan dari chunk terakhir saat constraint kembali terpenuhi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan siklus hidup background process Android dari Android 6 (Doze) hingga Android 14+ (Target SDK Restrictions).
- [ ] Kapan mutlak menggunakan WorkManager vs Coroutines vs Foreground Service vs AlarmManager.
- [ ] Arsitektur internal WorkManager: peran Room DB lokal, JobScheduler API binding, dan threading pool management.
- [ ] Kontrak jaminan eksekusi: Mengapa WorkManager menjamin *at-least-once*, bukan *exactly-once execution*.
- [ ] Siklus hidup `Worker` / `CoroutineWorker` (`doWork()`, `getForegroundInfo()`, handling cooperative cancellation via `onStopped()`).
- [ ] Perbedaan perilaku `ExistingWorkPolicy` (`REPLACE`, `KEEP`, `APPEND`, `APPEND_OR_REPLACE`).
- [ ] Karakteristik dan limitasi `PeriodicWorkRequest` (15 minutes boundary, flexible execution intervals).
- [ ] Cara kerja *Expedited Work*, kuota OS, dan fallback mechanism (`OutOfQuotaPolicy`).

### Saya tidak perlu menghafal:
- [ ] Nomor exact internal ID intent dari framework Android OS level rendah.
- [ ] Algoritma matematis native C++ kernel Android Binder IPC scheduler.
- [ ] Implementasi internal Room schema migrations milik internal WorkManager database (`workmanager.db`).

### Saya harus bisa melakukan:
- [ ] Menginisialisasi WorkManager secara custom menggunakan `Configuration.Provider` untuk dependency injection (Hilt/Koin).
- [ ] Mengonstruksi dependency chain bertingkat (`beginWith()`, `then()`, `combine()`) dengan data passing melalui `Data` / `workDataOf()`.
- [ ] Membangun custom exponential backoff policy untuk network recovery yang agresif namun aman terhadap baterai.
- [ ] Menulis integration/unit test untuk background workers menggunakan `work-testing` artifact dan `TestDriver`.
- [ ] Mendiagnosis isu WorkManager stuck atau gagal menggunakan `adb shell dumpsys jobscheduler`.
- [ ] Menerapkan pattern *Idempotency* pada client-server state sync untuk mencegah duplikasi data akibat proses retry otomatis.