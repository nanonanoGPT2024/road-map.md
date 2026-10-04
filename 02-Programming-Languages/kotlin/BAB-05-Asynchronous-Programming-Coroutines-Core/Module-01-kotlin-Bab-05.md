# Bab 05 Module 01 — Asynchronous Programming: Coroutines Core

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** `02-Programming-Languages`
* **Track:** Kotlin Core to Advanced
* **Bab:** 05 — Asynchronous & Concurrent Programming
* **Modul:** 01 — Asynchronous Programming: Coroutines Core
* **Tingkat Kesulitan:** Intermediate to Advanced
* **Prasyarat Pengetahuan:**
  * Pemahaman mendalam tentang JVM Memory Model dan Multi-threading dasar (`Thread`, `Runnable`, Thread Pool, Race Conditions).
  * Pemahaman Function Types, Lambdas dengan Receiver, dan Higher-Order Functions pada Kotlin.
  * Familiaritas dengan OOP & Functional Paradigm pada Kotlin (Interfaces, Sealed Classes, Generics).
* **Target Ekosistem:** Kotlin JVM (JDK 17/21) & Kotlin Multiplatform (KMP) baseline.
* **Dependensi Eksternal:** `org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0`

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Membedah Mekanisme Internal Coroutine:** Menguraikan proses transformasi *Continuation Passing Style* (CPS) dan *State Machine* yang di-generate oleh Kotlin Compiler pada fungsi yang ditandai dengan keyword `suspend`.
2. **Menguasai Prinsip Structured Concurrency:** Mengontrol siklus hidup eksekusi asinkron secara deterministik menggunakan hierarki `CoroutineScope`, `Job`, dan relasi *Parent-Child cancellation*.
3. **Mendisain Arsitektur Konkurensi Efisien:** Memilih dan mengonfigurasi `CoroutineDispatcher` (`Default`, `IO`, `Main`, `Unconfined`) sesuai profil beban komputasi (CPU-bound vs I/O-bound) tanpa memblokir thread sistem operasi.
4. **Menerapkan Mekanisme Cooperative Cancellation:** Membangun unit komputasi yang responsif terhadap sinyal pembatalan melalui pengecekan `isActive`, `ensureActive()`, atau `yield()`, serta menangani `CancellationException` dengan presisi.
5. **Menghubungkan & Mentransformasi Async Primitives:** Mengintegrasikan `async`/`await`, `launch`, dan `withContext` untuk mengelola agregasi data paralel dan *context switching* yang aman tanpa resiko *deadlock* atau *thread starvation*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Thread vs. Coroutine

Pada pemrograman konkurensi klasik (berbasis platform JVM Thread OS), model eksekusi bersifat **preemptive**: Kernel OS mengalokasikan *time slice* dan secara paksa melakukan *context switching* di antara thread. Setiap OS thread memakan alokasi memori yang signifikan (biasanya 1MB untuk stack frame native) dan biaya *context switch* kernel level yang mahal (menyimpan register CPU, flushes TLB, cache-miss).

Coroutine memperkenalkan model **cooperative multitasking** pada tingkat *user space*.

```
[ OS Kernel Space ]  -------------------------------------------------------------
                     Thread OS 1                     Thread OS 2
                          |                               |
[ JVM User Space ]   +----+----+                     +----+----+
                     | Coroutine A (Active)          | Coroutine C (Active)
                     | Coroutine B (Suspended)       | Coroutine D (Suspended)
                     +---------+                     +---------+
```

* **Thread adalah *Worker* (Pekerja):** Merupakan alokasi sumber daya komputasi native yang disediakan OS untuk mengeksekusi instruksi.
* **Coroutine adalah *Task* (Pekerjaan Ringan):** Merupakan unit eksekusi terisolasi yang dapat **berhenti sejenak (*suspend*)** tanpa melepaskan identitas pekerjaan, dan membebaskan worker (thread) untuk mengeksekusi coroutine lain. Ketika operasi I/O atau penundaan selesai, coroutine tersebut dapat dilanjutkan (*resume*) di thread yang sama atau thread yang sama sekali berbeda.

### Mental Model: Bookmark pada Buku (Continuation)

Bayangkan Anda membaca buku teknis (eksekusi kode) di meja belajar (thread). 
* **Model Blocking (Thread):** Anda menunggu kurir mengantar paket komponen hardware (I/O). Anda diam terpaku di meja belajar selama 2 jam, tidak melakukan apa pun, dan menolak siapa pun memakai meja tersebut.
* **Model Coroutine:** Anda menaruh penanda halaman (pembatas buku / `Continuation`) tepat pada baris yang Anda baca, menutup buku, dan meninggalkan meja belajar. Siswa lain dapat memakai meja tersebut. Ketika bel berbunyi tanda paket tiba, Anda mengambil buku Anda, membuka halaman bertanda, lalu melanjutkan membaca—bisa di meja belajar yang sama, atau pindah ke meja di lantai dua.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Eksekusi Coroutine dan Dispatching

Diagram berikut mengilustrasikan alur sejak coroutine di-launch, disuspensi oleh operasi I/O, hingga di-resume kembali oleh worker thread.

```
+-----------------------------------------------------------------------------------+
| Thread Pool (misal: Dispatchers.IO)                                               |
|                                                                                   |
|  Thread-1: [ Run Coroutine #1 ] ---> Menemui suspendPoint()                       |
|                                         |                                         |
|                                         v (Non-blocking Suspend)                  |
|                                    Simpan State ke Continuation                   |
|                                    Thread-1 BEBAS mengeksekusi Coroutine lain     |
+-----------------------------------------|-----------------------------------------+
                                          |
                        +-----------------+-----------------+
                        | Operasi Asinkron / Async I/O      |
                        | (Socket / DB / OS epoll / kqueue) |
                        +-----------------+-----------------+
                                          |
                                          v (Sinyal Selesai / OS Callback)
+-----------------------------------------------------------------------------------+
|  Dispatcher Worker Queue                                                          |
|                                                                                   |
|  Queue: [ Continuation(Coroutine #1, Result) ]                                    |
|              |                                                                    |
|              v                                                                    |
|  Thread-2: Mengambil Continuation dari Queue                                      |
|            Memanggil continuation.resumeWith(result)                              |
|            [ Eksekusi Coroutine #1 Berlanjut dari State Terakhir ]                |
+-----------------------------------------------------------------------------------+
```

### Pohon Konkurensi Terstruktur (Structured Concurrency Hierarchy)

```
                       +-----------------------------+
                       |   Root CoroutineScope       |
                       |   Job: Job-A                |
                       +--------------+--------------+
                                      |
              +-----------------------+-----------------------+
              |                                               |
              v                                               v
+---------------------------+                   +---------------------------+
| Child Scope (launch)      |                   | Child Scope (async)       |
| Job: Job-B (Child of A)   |                   | Job: Job-C (Child of A)   |
+-------------+-------------+                   +---------------------------+
              |
              v
+---------------------------+
| Grandchild (launch)       |
| Job: Job-D (Child of B)   |
+---------------------------+

ATURAN PERAMBATAN (PROPAGATION RULES):
1. Cancellation: Jika Job-A di-cancel, maka Job-B, Job-C, dan Job-D OTOMATIS batal.
2. Failure/Error: Jika Job-D melempar uncaught exception, error merambat naik ke Job-B,
   lalu ke Job-A, membatalkan seluruh saudara (Job-C) kecuali menggunakan SupervisorJob.
3. Completion: Job-A tidak akan berstatus 'Completed' sebelum Job-B, Job-C, dan Job-D selesai.
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Transformasi Kompiler: Continuation Passing Style (CPS)

Kotlin compiler mentranslasikan setiap fungsi yang memiliki keyword `suspend` dengan menyuntikkan parameter tambahan di akhir deklarasi fungsi: parameter `kotlin.coroutines.Continuation<T>`.

**Sebelum Kompilasi:**
```kotlin
suspend fun fetchUserProfile(userId: String): UserProfile
```

**Setelah Kompilasi (Representasi Bytecode / Java Signature):**
```java
// Tipe return berubah menjadi Object untuk mengakomodasi nilai asli 
// ATAU marker COROUTINE_SUSPENDED
Object fetchUserProfile(String userId, Continuation<? super UserProfile> completion);
```

Antarmuka `Continuation` didefinisikan secara internal di runtime Kotlin sebagai:

```kotlin
interface Continuation<in T> {
    val context: CoroutineContext
    fun resumeWith(result: Result<T>)
}
```

### The State Machine Transformation

Jika sebuah `suspend fun` memiliki beberapa titik suspensi (*suspension points*), compiler mengompilasi badan fungsi tersebut menjadi satu kelas turunan `CoroutineImpl` (berbasis *state machine* terindeks).

Perhatikan fungsi berikut:

```kotlin
suspend fun executePipeline(id: String): FinalResult {
    val token = requestToken(id)           // Suspension Point 1
    val rawData = fetchRawData(token)      // Suspension Point 2
    return processData(rawData)             // Regular Computation
}
```

Secara konseptual, compiler membentuk *state machine* seperti pseudo-code di bawah ini:

```java
// Pseudo-code rekonstruksi decompiled state machine
class ExecutePipelineStateMachine extends ContinuationImpl {
    Object result;
    int label = 0;
    String id;
    String token;
    Object rawData;

    ExecutePipelineStateMachine(Continuation completion) {
        super(completion);
    }

    @Override
    Object invokeSuspend(Object result) {
        this.result = result;
        this.label |= Integer.MIN_VALUE;
        return executePipeline(null, this);
    }
}

Object executePipeline(String id, Continuation completion) {
    ExecutePipelineStateMachine sm;
    
    // Periksa apakah completion sudah merupakan state machine yang sudah ada
    if (completion instanceof ExecutePipelineStateMachine) {
        sm = (ExecutePipelineStateMachine) completion;
        if ((sm.label & Integer.MIN_VALUE) != 0) {
            sm.label -= Integer.MIN_VALUE;
        }
    } else {
        // First invocation: inisialisasi state machine
        sm = new ExecutePipelineStateMachine(completion);
        sm.id = id;
    }

    switch (sm.label) {
        case 0:
            // Validasi pengecekan error dari pemanggilan sebelumnya
            throwOnFailure(sm.result);
            sm.label = 1;
            Object resToken = requestToken(sm.id, sm);
            if (resToken == COROUTINE_SUSPENDED) return COROUTINE_SUSPENDED;
            sm.result = resToken;
            // Jatuh ke case berikutnya jika eksekusi langsung sinkron (unlikely)
            
        case 1:
            throwOnFailure(sm.result);
            sm.token = (String) sm.result;
            sm.label = 2;
            Object resData = fetchRawData(sm.token, sm);
            if (resData == COROUTINE_SUSPENDED) return COROUTINE_SUSPENDED;
            sm.result = resData;

        case 2:
            throwOnFailure(sm.result);
            sm.rawData = sm.result;
            FinalResult finalRes = processData(sm.rawData);
            return finalRes; // Selesai, kembalikan hasil nyata ke caller

        default:
            throw new IllegalStateException("Call to 'resume' before 'invoke' with coroutine");
    }
}
```

Ketika fungsi mencapai operasi yang belum selesai (misalnya pembacaan I/O), fungsi mengembalikan sentinel khusus: `COROUTINE_SUSPENDED`. Thread tidak diblokir; ia langsung keluar dari frame eksekusi fungsi tersebut. Saat callback I/O selesai, threadpool akan mengeksekusi `sm.resumeWith(data)`, memicu `invokeSuspend()` pada State Machine dengan label berikutnya (melompat via `switch-case` ke `case 1` atau `case 2`), memulihkan variabel lokal yang tersimpan di field instance `sm`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. CoroutineContext & Elemen Penyusunnya

`CoroutineContext` adalah koleksi elemen berindeks unik (*indexed set*) yang mengonfigurasi perilaku eksekusi coroutine. Setiap elemen memiliki `Key` unik. Empat pilar utama `CoroutineContext`:

*   **`Job`:** Menangani siklus hidup (*lifecycle*), pembatalan (*cancellation*), dan relasi hirarki parent-child.
*   **`CoroutineDispatcher`:** Mengalokasikan thread mana yang akan digunakan untuk mengeksekusi instruksi coroutine.
*   **`CoroutineExceptionHandler`:** Handler opsional untuk menangkap *uncaught exceptions* pada coroutine root yang menggunakan builder `launch`.
*   **`CoroutineName`:** Penamaan eksplisit untuk kebutuhan tracing dan debugging.

Operasi aljabar context didukung melalui operator `+`:
```kotlin
val context = Dispatchers.IO + CoroutineName("BillingService") + Job()
val dispatcher = context[CoroutineDispatcher] // Lookup via Companion Object Key
```

### 2. Dispatchers Deep Dive

| Dispatcher | Thread Pool Backing | Rekomendasi Beban Kerja | Mekanisme Sizing |
| :--- | :--- | :--- | :--- |
| `Dispatchers.Default` | Shared background pool (Work-stealing pool) | CPU-Bound: JSON parsing, kompresi, enkripsi, kalkulasi matematis intensif. | Ukuran thread pool = Jumlah Core CPU (minimal 2). |
| `Dispatchers.IO` | On-demand dynamic elastic pool (berbagi thread dengan Default jika memungkinkan) | Blocking I/O: File read/write, Database query blocking (JDBC), Network HTTP synchronous calls. | Default: `max(64, jumlah core CPU)`. Dapat ditingkatkan via JVM property. |
| `Dispatchers.Main` | Single thread UI loop (Android Looper, JavaFX Application Thread, Swing EventQueue). | Interaksi UI, event handling cepat, rendering trigger. | 1 Thread khusus UI platform. |
| `Dispatchers.Unconfined` | Tidak dibatasi thread manapun. | Operasi yang tidak memakan biaya komputasi, strictly event-driven tanpa modifikasi shared mutable state. | Berjalan di thread pemanggil hingga titik suspensi pertama. Setelah resume, berjalan di thread yang meresume. |

### 3. Builders: `launch` vs `async` vs `runBlocking`

*   **`launch` (Fire-and-forget):**
    *   Return type: `Job`.
    *   Digunakan ketika hasil kembalian tidak dibutuhkan secara langsung.
    *   Exception yang tidak ditangani langsung dirambatkan ke atas (*escalated*) ke parent context.
*   **`async` (Async computation with result):**
    *   Return type: `Deferred<T>` (subtipe dari `Job`).
    *   Digunakan untuk eksekusi paralel yang nilainya akan diambil menggunakan suspensi `.await()`.
    *   Exception ditahan (*encapsulated*) di dalam objek `Deferred` dan baru dilempar kembali ketika `.await()` dieksekusi.
*   **`runBlocking` (Bridge ke Synchronous World):**
    *   Return type: `T`.
    *   Memblokir thread OS pemanggil hingga seluruh coroutine di dalam bloknya tuntas.
    *   **Anti-pattern** pada production path backend/UI, hanya boleh digunakan di `fun main()` atau testing baseline unit.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah program mandiri lengkap yang mendemonstrasikan orkestrasi `CoroutineScope`, `launch`, `async`, `withContext`, serta penanganan eksepsi.

```kotlin
package com.architect.coroutines.core

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineName
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import java.time.Instant

data class UserAccount(val id: String, val username: String)
data class CreditScore(val score: Int, val isEligible: Boolean)
data class LoanApplicationResult(val account: UserAccount, val credit: CreditScore, val status: String)

class LoanAssessmentEngine(
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
    private val cpuDispatcher: CoroutineDispatcher = Dispatchers.Default
) {
    // Custom Exception Handler untuk Scope Root
    private val exceptionHandler = CoroutineExceptionHandler { _, throwable ->
        println("[CRITICAL ERROR] Handler menangkap fatal error: ${throwable.message}")
    }

    // Definisi Scope Terstruktur Mandiri
    private val engineScope = CoroutineScope(SupervisorJob() + cpuDispatcher + CoroutineName("LoanEngineScope") + exceptionHandler)

    suspend fun fetchAccount(userId: String): UserAccount = withContext(ioDispatcher) {
        println("[${Thread.currentThread().name}] Mengambil UserAccount untuk: $userId")
        delay(300) // Simulasi latency jaringan/DB non-blocking
        UserAccount(id = userId, username = "john_dev")
    }

    suspend fun calculateCreditScore(userId: String): CreditScore = withContext(ioDispatcher) {
        println("[${Thread.currentThread().name}] Menghitung CreditScore untuk: $userId")
        delay(500) // Simulasi query credit scoring
        CreditScore(score = 750, isEligible = true)
    }

    suspend fun evaluateApplication(userId: String): LoanApplicationResult = withContext(cpuDispatcher) {
        println("[${Thread.currentThread().name}] Mulai evaluasi aplikasi pinjaman...")

        // Dekomposisi Konkurensi Paralel menggunakan async
        val accountDeferred: Deferred<UserAccount> = async {
            fetchAccount(userId)
        }

        val creditDeferred: Deferred<CreditScore> = async {
            calculateCreditScore(userId)
        }

        // Menunggu hasil kedua task secara paralel via await()
        val account = accountDeferred.await()
        val credit = creditDeferred.await()

        println("[${Thread.currentThread().name}] Menggabungkan hasil di Dispatchers.Default")
        val status = if (credit.isEligible && credit.score >= 700) "APPROVED" else "REJECTED"

        LoanApplicationResult(account, credit, status)
    }

    fun submitBackgroundAudit(applicationId: String): Job {
        return engineScope.launch {
            println("[${Thread.currentThread().name}] Memulai Audit Background: $applicationId")
            var progress = 0
            while (progress < 100) {
                // Menjamin kooperatif terhadap pembatalan
                ensureActive()
                delay(100)
                progress += 25
                println("[${Thread.currentThread().name}] Audit $applicationId berjalan: $progress%")
            }
            println("[${Thread.currentThread().name}] Audit $applicationId SELESAI")
        }
    }

    fun shutdown() {
        val job = engineScope.coroutineContext[Job]
        job?.cancel()
        println("LoanAssessmentEngine Scope dibatalkan secara bersih.")
    }
}

fun main() = runBlocking {
    println("=== START APLIKASI COROUTINE CORE ===")
    val engine = LoanAssessmentEngine()

    // 1. Eksekusi Asinkron Paralel (Sequential decomposition)
    val startTimestamp = Instant.now().toEpochMilli()
    val result = engine.evaluateApplication("USER-8891")
    val duration = Instant.now().toEpochMilli() - startTimestamp

    println("Hasil: $result")
    println("Total waktu eksekusi paralel: ${duration}ms (Sekitar ~500ms, bukan 800ms)")

    // 2. Eksekusi Background Fire-and-Forget dan Cooperative Cancellation
    println("\n=== DEMO PENGUJIAN CANCELLATION ===")
    val auditJob = engine.submitBackgroundAudit("AUDIT-9900")
    
    delay(220) // Biarkan audit berjalan sebagian (mencapai ~50%)
    println("Membatalkan background audit secara paksa...")
    auditJob.cancelAndJoin()
    println("Status Job Audit: isCancelled=${auditJob.isCancelled}, isCompleted=${auditJob.isCompleted}")

    engine.shutdown()
    println("=== SELESAI ===")
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari komponen utama kode di atas:

1.  **Baris 24:** `private val engineScope = CoroutineScope(SupervisorJob() + cpuDispatcher + CoroutineName("LoanEngineScope") + exceptionHandler)`
    *   Menciptakan lifecycle runtime terisolasi. Menggunakan `SupervisorJob()` memastikan kegagalan pada salah satu child job yang di-*spawn* tidak mematikan seluruh scope engine, melainkan didelegasikan ke `exceptionHandler`.
2.  **Baris 26:** `suspend fun fetchAccount(...) = withContext(ioDispatcher)`
    *   `withContext` mengeksekusi blok kode dengan dispatcher berbeda (`Dispatchers.IO`), menunda pemanggil hingga selesai, lalu secara atomik memulihkan context pemanggil. Ini menjamin *main-safety* atau *caller-safety* (fungsi suspend tidak boleh memblokir thread pemanggil).
3.  **Baris 38:** `val accountDeferred: Deferred<UserAccount> = async { fetchAccount(userId) }`
    *   Mengeksekusi `fetchAccount` secara concurrent di background threadpool. Pemanggilan ini tidak menahan eksekusi baris berikutnya.
4.  **Baris 42:** `val creditDeferred: Deferred<CreditScore> = async { calculateCreditScore(userId) }`
    *   Dijalankan bersamaan dengan `accountDeferred`. Waktu total yang dibutuhkan kedua operasi adalah $\max(\text{delay}_1, \text{delay}_2) = 500\text{ms}$, bukan $300 + 500 = 800\text{ms}$.
5.  **Baris 46-47:** `val account = accountDeferred.await()`; `val credit = creditDeferred.await()`
    *   Suspension points. Jika data belum tersedia, coroutine evaluator melepaskan thread worker. Begitu data tiba, state machine kembali berjalan.
6.  **Baris 61:** `ensureActive()`
    *   Memeriksa status `Job.isActive`. Jika coroutine telah dibatalkan via `cancel()`, fungsi ini melempar `CancellationException` internal secara instan, mencegah CPU membakar siklus untuk komputasi sia-sia.
7.  **Baris 89:** `auditJob.cancelAndJoin()`
    *   Mengirim sinyal pembatalan ke coroutine target dan menunda pemanggil sampai job benar-benar beralih ke state *Terminated* (menyelesaikan blok `finally` jika ada).

---

## SEKSI 09 — STUDI KASUS NYATA

### Pipeline Agregasi Profil Finansial Skala Besar (Fintech Gateway)

#### Skenario
Sebuah institusi finansial membangun payment aggregator backend yang menangani ratusan transaksi per detik. Saat user mengajukan checkout, backend harus mengagregasi data dari 3 microservices independen:
1. **Core Banking Service:** Mengecek saldo rekening (High priority, SLA 150ms).
2. **Fraud Detection Engine:** Menghitung Risk Score transaksi (High priority, SLA 200ms).
3. **Loyalty System:** Mengambil poin reward (Low priority, SLA 400ms).

#### Kendala Arsitektur
*   Jika menggunakan Thread-per-request blocking (model Java EE / Tomcat standar), kapasitas 200 concurrent threads akan habis seketika saat salah satu downstream microservice mengalami latensi 2 detik (*Thread Starvation*).
*   Jika Fraud Engine menyatakan "BLOCKED", kita harus membatalkan pemanggilan Core Banking dan Loyalty secara real-time untuk memotong latensi dan tidak membuang bandwidth server.
*   Loyalty point bersifat *optional/best-effort*: jika gagal atau timeout, transaksi tetap boleh dilanjutkan dengan poin 0. Kegagalan Loyalty tidak boleh menggagalkan agregasi utama.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi *production-ready* menggunakan coroutines core engine, mencakup custom context, structured concurrency, dan graceful degradation.

```kotlin
package com.architect.coroutines.production

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineName
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.IOException

// Model Domain
data class PaymentContext(val transactionId: String, val customerId: String, val amount: Double)
data class BalanceInfo(val availableAmount: Double, val currency: String)
data class FraudCheck(val isBlacklisted: Boolean, val riskLevel: String)
data class LoyaltyProfile(val points: Long)

data class AggregatedPaymentProfile(
    val transactionId: String,
    val balance: BalanceInfo,
    val fraudCheck: FraudCheck,
    val loyaltyProfile: LoyaltyProfile
)

// Custom Business Exceptions
class HighRiskFraudException(message: String) : RuntimeException(message)
class InsufficientFundsException(message: String) : RuntimeException(message)

interface DownstreamGateway {
    suspend fun getBalance(customerId: String): BalanceInfo
    suspend fun getFraudStatus(customerId: String, amount: Double): FraudCheck
    suspend fun getLoyaltyPoints(customerId: String): LoyaltyProfile
}

// Implementasi Mock dengan Latensi Asinkron
class HttpDownstreamGateway(private val ioDispatcher: CoroutineDispatcher) : DownstreamGateway {
    override suspend fun getBalance(customerId: String): BalanceInfo = withContext(ioDispatcher) {
        delay(120) // simulasi response time
        BalanceInfo(availableAmount = 5000.0, currency = "USD")
    }

    override suspend fun getFraudStatus(customerId: String, amount: Double): FraudCheck = withContext(ioDispatcher) {
        delay(180) // simulasi compute time fraud network
        if (amount > 10000.0) {
            FraudCheck(isBlacklisted = true, riskLevel = "CRITICAL")
        } else {
            FraudCheck(isBlacklisted = false, riskLevel = "LOW")
        }
    }

    override suspend fun getLoyaltyPoints(customerId: String): LoyaltyProfile = withContext(ioDispatcher) {
        delay(350) // simulasi layanan legacy yang lambat
        LoyaltyProfile(points = 1250)
    }
}

class PaymentAggregatorService(
    private val gateway: DownstreamGateway,
    private val defaultDispatcher: CoroutineDispatcher = Dispatchers.Default
) {
    suspend fun aggregatePaymentData(context: PaymentContext): AggregatedPaymentProfile = coroutineScope {
        // coroutineScope menjamin Structured Concurrency:
        // Jika ada child yang melempar exception tak tertangani, semua saudara dibatalkan otomatis.

        println("[AGGREGATOR] Mulai memproses transaksi: ${context.transactionId} pada coroutine: ${coroutineContext[CoroutineName]}")

        // 1. Fetch Fraud Check (Critical Path)
        val fraudDeferred: Deferred<FraudCheck> = async(defaultDispatcher + CoroutineName("Async-Fraud")) {
            withTimeout(300) {
                gateway.getFraudStatus(context.customerId, context.amount)
            }
        }

        // 2. Fetch Balance (Critical Path)
        val balanceDeferred: Deferred<BalanceInfo> = async(defaultDispatcher + CoroutineName("Async-Balance")) {
            withTimeout(300) {
                gateway.getBalance(context.customerId)
            }
        }

        // 3. Fetch Loyalty (Optional Path / Non-critical)
        // Kita tangani error di dalam coroutine child agar tidak membatalkan coroutineScope parent
        val loyaltyDeferred: Deferred<LoyaltyProfile> = async(defaultDispatcher + CoroutineName("Async-Loyalty")) {
            try {
                withTimeout(200) { // SLA ketat untuk data sekunder
                    gateway.getLoyaltyPoints(context.customerId)
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e // WAJIB rethrow cancellation exception!
                println("[WARN] Gagal mengambil profil Loyalty (${e.message}). Menggunakan fallback 0 poin.")
                LoyaltyProfile(points = 0)
            }
        }

        // Evaluasi Fail-Fast: Validasi Fraud
        val fraudResult = fraudDeferred.await()
        if (fraudResult.isBlacklisted) {
            // Membatalkan child jobs yang belum selesai secara otomatis karena kita melempar exception di coroutineScope
            throw HighRiskFraudException("Transaksi DITOLAK! Terdeteksi Fraud dengan tingkat: ${fraudResult.riskLevel}")
        }

        // Validasi Saldo
        val balanceResult = balanceDeferred.await()
        if (balanceResult.availableAmount < context.amount) {
            throw InsufficientFundsException("Saldo tidak mencukupi untuk transaksi: ${context.transactionId}")
        }

        val loyaltyResult = loyaltyDeferred.await()

        AggregatedPaymentProfile(
            transactionId = context.transactionId,
            balance = balanceResult,
            fraudCheck = fraudResult,
            loyaltyProfile = loyaltyResult
        )
    }
}

// Runtime Execution Test Driver
fun main() = kotlinx.coroutines.runBlocking {
    val gateway = HttpDownstreamGateway(Dispatchers.IO)
    val service = PaymentAggregatorService(gateway)

    println("--- SKENARIO 1: TRANSAKSI VALID ---")
    val validContext = PaymentContext("TX-1001", "CUST-A", 150.0)
    try {
        val result = service.aggregatePaymentData(validContext)
        println("Transaksi Berhasil Dimuat: $result")
    } catch (e: Exception) {
        println("Transaksi Gagal: ${e.message}")
    }

    println("\n--- SKENARIO 2: TRANSAKSI FRAUD (FAIL-FAST) ---")
    val fraudContext = PaymentContext("TX-6666", "CUST-EVIL", 50000.0)
    try {
        service.aggregatePaymentData(fraudContext)
    } catch (e: HighRiskFraudException) {
        println("Intercepted Exception Sukses: ${e.message}")
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektur | OS Native Threads | Kotlin Coroutines | Reactive Streams (RxJava / Reactor) | Java Virtual Threads (Project Loom) |
| :--- | :--- | :--- | :--- | :--- |
| **Memory Footprint** | ~1MB per thread stack. Rawan `OutOfMemoryError` pada >5000 thread. | ~beberapa KB per coroutine frame (heap object). Mampu menampung jutaan coroutine. | Sangat ringan, overhead berbasis subscription pipeline objek. | ~beberapa KB per virtual thread, dialokasikan di heap JVM. |
| **Gaya Penulisan Kode** | Imperatif blocking (`Thread.sleep()`). Mudah dibaca, buruk dalam skalabilitas. | Sequential imperative style (`suspend fun`), non-blocking di belakang layar. | Deklaratif fungsional (monadic chains: `.flatMap()`, `.zip()`). *Steep learning curve*, *callback hell* terselubung. | Imperatif murni blocking (`Thread.sleep()` tanpa blocking OS thread). Kode legacy compatible tanpa rewrite. |
| **Debugging & Stack Trace** | Sangat jelas, stack trace merefleksikan seluruh alur eksekusi sinkron. | Diperlukan `kotlinx-coroutines-debug`. CPS memutus rantai native stack trace standar. | Buruk secara default. Membutuhkan assembly tracing hooks khusus (e.g., `Hooks.onOperatorDebug()`). | Sangat baik, stack trace menyerupai thread native standar JVM. |
| **Cancellation Handling** | Menggunakan interrupt flag (`Thread.interrupt()`). Sering diabaikan atau disalahgunakan. | Built-in via Cooperative Cancellation (`CancellationException`) & Structured Concurrency. | Ekplisit via pemutusan subscription (`Disposable.dispose()`). | Otomatis terintegrasi via interrupt semantics pada standard blocking API JVM. |
| **Ecosystem Portability** | Terikat eksklusif ke platform OS/JVM. | Multiplatform (JVM, Android, Native C/LLVM, JavaScript, WASM). | Terbatas ke JVM (kecuali RxJS/RxSwift yang berdiri sebagai engine terpisah). | Eksklusif untuk JVM runtime (hanya tersedia di Java 21+). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Menelan `CancellationException` (The Silent Resuscitation Trap)

Ketika parent coroutine dibatalkan, pembatalan dikomunikasikan ke child coroutine dengan melempar `kotlinx.coroutines.CancellationException` di titik suspensi berikutnya (`delay`, `yield`, `await`). 

Jika Anda membungkus operasi dengan `try-catch (e: Exception)` generik tanpa melempar kembali `CancellationException`, coroutine tersebut menolak untuk mati, merusak siklus Structured Concurrency.

```kotlin
// BAHAYA BESAR / ANTI-PATTERN
launch {
    try {
        doLongRunningIoOperation()
    } catch (e: Exception) { // CancellationException adalah turunan dari IllegalStateException -> Exception
        // Log ini akan menelan CancellationException!
        logger.error("Terjadi error", e)
    }
}

// SOLUSI BENAR
launch {
    try {
        doLongRunningIoOperation()
    } catch (e: CancellationException) {
        throw e // Lempar kembali agar parent mengenali pembatalan!
    } catch (e: Exception) {
        logger.error("Terjadi business/IO error", e)
    }
}
```

### 2. Unconfined Dispatcher Leakage

Penggunaan `Dispatchers.Unconfined` tampak menarik karena tidak menimbulkan overhead context switching. Namun, coroutine yang menggunakan unconfined dispatcher akan berlanjut di thread mana pun yang memanggil `resume()`. 

Jika Anda memulai coroutine di Main Thread, lalu memanggil suspend function yang di-resume oleh event thread internal Netty, kode Anda berikutnya setelah suspension point akan dieksekusi di thread Netty tersebut. Ini berpotensi merusak keamanan UI thread atau membebani IO event loop.

### 3. Thread Starvation pada Blocking Calls di `Dispatchers.Default`

`Dispatchers.Default` memiliki thread yang dibatasi sebanyak jumlah CPU core. Jika Anda memanggil method blocking legacy (seperti `Thread.sleep()`, JDBC executeQuery, atau Apache HttpClient blocking call) di dalam `Dispatchers.Default`:
Seluruh worker pool akan membeku. Coroutine CPU lain (kalkulasi, rendering) tidak akan mendapatkan giliran eksekusi. Gunakan selalu `withContext(Dispatchers.IO)` untuk memindahkan eksekusi blocking ke thread pool elastis.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Memutus Rantai Konkurensi dengan `GlobalScope`

```kotlin
// BAD: Memory leak, tidak terikat lifecycle komponen, tidak bisa dibatalkan secara kolektif
fun processData() {
    GlobalScope.launch { 
        repository.save()
    }
}

// GOOD: Injeksi CoroutineScope eksplisit atau gunakan Structured Concurrency
class DataProcessor(private val applicationScope: CoroutineScope) {
    fun processData() {
        applicationScope.launch {
            repository.save()
        }
    }
}
```

### Kesalahan 2: Menggunakan `async` Saat Tidak Membutuhkan Hasil (`Deferred`)

```kotlin
// BAD: Jika function gagal, exception akan ditelan sampai ada yang memanggil await(),
// atau bocor tanpa penanganan terstruktur.
scope.async {
    analyticsService.trackEvent("CLICK")
}

// GOOD: Gunakan launch untuk operasi fire-and-forget
scope.launch {
    analyticsService.trackEvent("CLICK")
}
```

### Kesalahan 3: Tidak Menangani Cooperative Cancellation pada CPU-Bound Loop

```kotlin
// BAD: Loop ini TIDAK BISA dibatalkan meskipun scope.cancel() dipanggil!
// Loop tidak memiliki titik suspensi.
launch(Dispatchers.Default) {
    while (dataAvailable) {
        computeHeavyHash() 
    }
}

// GOOD: Periksa status keaktifan atau berikan yield
launch(Dispatchers.Default) {
    while (dataAvailable) {
        ensureActive() // Langsung throw CancellationException jika job di-cancel
        computeHeavyHash()
        // ATAU: yield() untuk memberi kesempatan coroutine lain berjalan
    }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Suspending Functions Harus Safe Dijalanlan dari Caller Manapun (*Main-Safe*):**
   Fungsi dengan modifier `suspend` tidak boleh memblokir thread pemanggil. Jika fungsi Anda menjalankan komputasi berat atau blocking I/O, selalu bungkus secara internal dengan `withContext(Dispatchers.IO)` atau `withContext(Dispatchers.Default)`. Caller tidak boleh dipaksa mengingat dispatcher apa yang harus digunakan.

   ```kotlin
   // Standar Industri
   class UserRepository(private val api: UserApi, private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO) {
       suspend fun getUser(id: String): User = withContext(ioDispatcher) {
           api.fetchUser(id) // Dijamin aman dipanggil dari thread mana pun
       }
   }
   ```

2. **Jangan Mengembalikan Objek `Job` dari Suspend Function:**
   Sebuah `suspend fun` harus mengembalikan nilai secara sinkron-konseptual atau selesai ketika tugasnya usai. Jika Anda mengembalikan `Job`, caller kehilangan kendali atas lifecycle dan struktur hierarki. Hindari signature seperti: `suspend fun doWork(): Job`.

3. **Injeksi `CoroutineDispatcher` untuk Kemudahan Testing:**
   Jangan pernah melakukan hardcoding `Dispatchers.IO` atau `Dispatchers.Default` langsung di dalam kelas domain/bisnis. Selalu injeksikan via constructor injection. Ini memungkinkan penggantian dengan `StandardTestDispatcher` atau `UnconfinedTestDispatcher` saat menjalankan unit testing.

4. **Pertahankan Konvensi Parent-Child Lifecycle Menggunakan `coroutineScope`:**
   Jika Anda membutuhkan sub-task konkuren di dalam fungsi suspend, gunakan pembungkus `coroutineScope { }`. Pembungkus ini memastikan fungsi tidak akan kembali (*return*) sebelum seluruh child coroutines yang di-launch di dalamnya selesai.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Dynamic I/O Limiter via Dispatcher Sizing

Secara default, `Dispatchers.IO` mendukung hingga 64 thread (atau jumlah core, mana yang lebih besar). Jika aplikasi Anda memanggil downstream database mikro yang hanya mampu menerima 10 koneksi konkuren pool, mengirimkan 64 query simultan via `Dispatchers.IO` akan menyebabkan antrean berat dan timeout di layer database pool.

Gunakan ekstensi `.limitedParallelism()` untuk membatasi konkurensi tanpa membuat thread pool baru:

```kotlin
class DatabaseRepository(private val dbConnectionPoolSize: Int = 10) {
    // Membatasi konkurensi Dispatchers.IO hanya menggunakan maksimal 10 thread
    // Mengeliminasi overhead thread contention dan menjaga resource downstream
    private val dbDispatcher = Dispatchers.IO.limitedParallelism(dbConnectionPoolSize)

    suspend fun executeQuery(sql: String): QueryResult = withContext(dbDispatcher) {
        runBlockingJdbcCall(sql)
    }
}
```

### Alokasi Objek State Machine Minimization

Compiler membuat instance `Continuation` baru setiap kali suspend function dipanggil dan disuspensi. Untuk path yang sangat kritis (high-throughput low-latency network gateways):
* Hindari mendekomposisi kode suspend ke dalam fungsi-fungsi suspend mikro yang terlalu banyak jika eksekusinya murni sinkron (tidak ada delay atau async nyata).
* Manfaatkan `suspendCoroutineUninterceptedOrReturn` hanya pada tingkat library internal jika ingin menghindari alokasi alur suspensi ketika hasil sudah langsung tersedia (*immediate value*).

---

## SEKSI 16 — KEAMANAN & HARDENING

### Penularan Konteks Keamanan (Security Context & ThreadLocal Propagation)

Dalam sistem berbasis kerangka kerja enterprise (seperti Spring Security), kredensial otentikasi disimpan di dalam `ThreadLocal`. Karena coroutine berpindah-pindah thread selama eksekusi (*thread hopping*), `ThreadLocal` akan tertinggal dan menyebabkan otentikasi bernilai `null` atau bocor ke pengguna lain.

**Solusi Hardening: Gunakan Coroutine ThreadContextElement**

```kotlin
import kotlinx.coroutines.asContextElement

// Misalkan SecurityContextHolder menyimpan security identity
val securityContext = SecurityContextHolder.getContext()

// Konversikan ThreadLocal ke CoroutineContext Element
val contextElement = SecurityContextHolder.threadLocalContext.asContextElement(securityContext)

// Sekarang eksekusi aman berpindah-pindah thread tanpa kehilangan context keamanan
engineScope.launch(contextElement) {
    // ThreadLocal dipastikan sinkron di thread manapun coroutine ini melompat
    securedBankingOperation()
}
```

### Mitigasi Serangan DoS via Uncontrolled Async Spawning

Jangan pernah melakukan mapping data input pengguna langsung ke `async` tanpa pembatasan jumlah concurrency:

```kotlin
// RENTAN TERHADAP MEMORY EXHAUSTION DOS
fun processUserUploads(items: List<UploadItem>) {
    items.forEach { item ->
        scope.launch { process(item) } // Jika items.size == 1.000.000, alokasi heap meledak
    }
}

// HARDENED MENGGUNAKAN CONCURRENCY THROTTLING
suspend fun processUserUploadsHardened(items: List<UploadItem>, maxConcurrentUploads: Int = 20) {
    val semaphore = kotlinx.coroutines.sync.Semaphore(maxConcurrentUploads)
    coroutineScope {
        items.forEach { item ->
            launch {
                semaphore.withPermit {
                    process(item)
                }
            }
        }
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. MDC (Mapped Diagnostic Context) Logging Propagation

Untuk pelacakan terpusat (ELK, Datadog), `traceId` harus ada di setiap line log. Modul `kotlinx-coroutines-slf4j` menyediakan adapter bridge untuk menyinkronkan MDC antar thread suspension:

```kotlin
import kotlinx.coroutines.slf4j.MDCContext
import org.slf4j.MDC

fun handleHttpRequest(traceId: String) {
    MDC.put("traceId", traceId)
    
    // MDCContext() menangkap snapshot MDC saat ini dan memasukkannya ke context coroutine
    val requestScope = CoroutineScope(Dispatchers.Default + MDCContext())
    
    requestScope.launch {
        logger.info("Log ini mencetak traceId secara tepat, meskipun berpindah worker thread!")
        withContext(Dispatchers.IO) {
            logger.info("Tetap mencetak traceId yang sama di Thread IO")
        }
    }
}
```

### 2. Debugging JVM Arguments

Aktifkan coroutine debugger saat runtime local dengan menyuntikkan argumen JVM berikut:
```bash
-Dkotlinx.coroutines.debug
```
Ketika flag ini aktif, nama thread OS akan otomatis dianotasi dengan nama dan ID coroutine yang sedang berjalan:
`Thread-1 @BillingService#2` alih-alih hanya `Thread-1`.

### 3. Dump Coroutines Aktif Secara Programatik

```kotlin
import kotlinx.coroutines.debug.DebugProbes

fun initializeDebugging() {
    DebugProbes.install()
}

fun printActiveCoroutines() {
    // Mencetak struktur pohon hierarki coroutine, state (SUSPENDED/RUNNING), dan stack trace aslinya
    DebugProbes.dumpCoroutines()
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Tabel Komparasi Primitif Coroutine

| Primitif | Return Value | Blocking/Suspending | Failure Propagation | Kapan Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| `launch { }` | `Job` | Non-blocking (Return instan) | Merambat naik ke parent langsung | Menjalankan task latar belakang yang berdiri sendiri (fire-and-forget). |
| `async { }` | `Deferred<T>` | Non-blocking (Return instan) | Menggagalkan parent JIKA dipanggil di dalam `coroutineScope`, error dilempar ulang saat `.await()`. | Komputasi data paralel yang nilainya perlu digabungkan. |
| `withContext(ctx)`| `T` (Nilai blok) | Suspending | Merambat langsung ke pemanggil via exception throwing standar | Pergantian thread pool (context switching) sementara untuk I/O atau CPU. |
| `coroutineScope { }`| `T` (Nilai blok) | Suspending | Menunggu seluruh child tuntas; gagal jika salah satu child gagal | Mendekomposisi pekerjaan paralel di dalam `suspend fun`. |
| `supervisorScope { }`| `T` (Nilai blok) | Suspending | Kegagalan salah satu child TIDAK mematikan child lain | Menjalankan kumpulan tugas independen yang boleh gagal sebagian. |

### Cheatsheet Aturan Emas (Golden Rules)
1. **Never catch `Throwable` or `Exception` blindly:** Selalu lempar kembali `CancellationException`.
2. **Never block inside suspending functions:** Ganti `Thread.sleep()` dengan `delay()`.
3. **Always prefer Structured Concurrency:** Jangan biarkan coroutine terisolasi tanpa parent scope yang terdefinisi siklus hidupnya.
4. **Main-Safety is paramount:** Setiap fungsi `suspend` harus aman dieksekusi dari caller mana pun (bungkus I/O dengan context IO).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji pemahaman Anda terhadap arsitektur dasar Kotlin Coroutines di bawah ini.

### Soal Pilihan Ganda (Basic - Intermediate)

#### Q1 (Basic)
Apa yang terjadi pada level OS Thread ketika sebuah coroutine mengeksekusi instruksi `delay(1000)`?
* A) Thread OS diblokir dan masuk ke kondisi `TIMED_WAITING` selama 1 detik.
* B) Thread OS dialokasikan ke proses kernel lain dan dihapus dari memori JVM.
* C) Thread OS dilepaskan untuk mengeksekusi coroutine lain; timer internal dijadwalkan untuk menjadwalkan ulang kelanjutan eksekusi coroutine tersebut setelah 1 detik.
* D) Sebuah thread native OS baru diinstansiasi secara khusus untuk menghitung mundur durasi 1 detik.

#### Q2 (Basic)
Manakah dispatcher yang paling tepat digunakan untuk membaca file berukuran 500MB dari media penyimpanan disk lokal?
* A) `Dispatchers.Default`
* B) `Dispatchers.Main`
* C) `Dispatchers.Unconfined`
* D) `Dispatchers.IO`

#### Q3 (Intermediate)
Perhatikan potongan kode berikut:
```kotlin
val scope = CoroutineScope(Job())
scope.launch {
    try {
        delay(5000)
        println("Task Finished")
    } catch (e: Exception) {
        println("Catch Error: ${e.javaClass.simpleName}")
    }
}
delay(1000)
scope.cancel()
```
Apa output yang akan tercetak di konsol?
* A) "Task Finished"
* B) "Catch Error: CancellationException"
* C) Tidak mencetak apapun karena coroutine langsung dihentikan paksa seketika.
* D) Program melempar crash `IllegalStateException` di thread utama.

#### Q4 (Intermediate)
Bagaimana representasi bytecode Java hasil kompilasi dari fungsi suspend `suspend fun calculate(value: Int): String`?
* A) `public final String calculate(int value)`
* B) `public final Object calculate(int value, Continuation<? super String> $completion)`
* C) `public final CompletableFuture<String> calculate(int value)`
* D) `public final void calculate(int value, Function1<String, Void> callback)`

#### Q5 (Basic)
Apa fungsi utama dari `SupervisorJob()` jika dibandingkan dengan `Job()` standar?
* A) Mempercepat alokasi memori CPU untuk coroutine prioritas tinggi.
* B) Mengizinkan coroutine memotong antrean pada pool `Dispatchers.Default`.
* C) Mencegah kegagalan (uncaught exception) pada salah satu child job membatalkan parent job dan child job saudaranya.
* D) Mengubah thread pool yang digunakan menjadi single thread berprioritas real-time.

---

### Soal Analisis Masalah Kode (Intermediate)

#### Q6 (Intermediate - Root Cause Analysis)
Perhatikan blok kode di bawah ini:
```kotlin
suspend fun fetchDashboardData(): Dashboard = coroutineScope {
    val profile = async { api.getProfile() }
    val metrics = async { 
        throw NetworkException("Connection Reset")
        api.getMetrics() 
    }
    
    Dashboard(profile.await(), metrics.await())
}
```
Jika `api.getMetrics()` melempar exception `NetworkException`, apa yang terjadi pada task `api.getProfile()`?
* A) `api.getProfile()` akan tetap berjalan hingga selesai di latar belakang tanpa terpengaruh.
* B) `api.getProfile()` akan dibatalkan secara kooperatif oleh mekanisme structured concurrency karena kegagalan pada saudara kandungnya di dalam `coroutineScope`.
* C) Aplikasi mengalami deadlock karena `Dashboard` menunggu `profile.await()`.
* D) Seluruh CoroutineScope di root aplikasi ditutup permanen.

#### Q7 (Intermediate)
Manakah teknik yang tepat untuk membuat sebuah loop kalkulasi CPU-intensive responsif terhadap pembatalan coroutine?
* A) Menyisipkan instruksi `Thread.sleep(0)`.
* B) Memanggil `yield()` atau `ensureActive()` secara periodik di dalam badan loop.
* C) Mengubah loop menjadi rekursif murni.
* D) Memindahkan loop ke dalam blok `runBlocking`.

#### Q8 (Intermediate)
Mengapa pemanggilan fungsi `runBlocking` di dalam REST controller (misal Spring Boot atau Ktor) sangat tidak disarankan?
* A) Karena `runBlocking` tidak mendukung context passing.
* B) Karena `runBlocking` mengabaikan penggunaan `SupervisorJob`.
* C) Karena `runBlocking` memblokir thread eksekutor OS yang mendasarinya, meniadakan efisiensi throughput non-blocking framework.
* D) Karena `runBlocking` selalu melempar `CancellationException` secara acak.

#### Q9 (Intermediate)
Apa perbedaan mendasar dalam penanganan error antara `launch` dan `async` jika dijalankan langsung di bawah root `CoroutineScope` mandiri?
* A) `launch` membuang exception tanpa jejak, `async` melemparnya langsung ke console.
* B) `launch` merambatkan exception yang tidak tertangkap langsung ke `CoroutineExceptionHandler` atau thread uncaught handler; sedangkan `async` merangkum exception di objek `Deferred` dan baru melemparkannya kembali saat fungsi `.await()` dipanggil.
* C) `async` tidak bisa mengalami kegagalan/error.
* D) `launch` otomatis mengulangi (*retry*) proses yang gagal hingga 3 kali.

#### Q10 (Intermediate)
Apa fungsi dari ekstensi `.limitedParallelism(x)` yang diperkenalkan pada coroutine dispatcher?
* A) Memaksa coroutine berjalan pada arsitektur CPU 32-bit.
* B) Membuat thread OS baru sejumlah `x` thread secara eksklusif.
* C) Membatasi konkurensi maksimum eksekusi task sebesar `x` tanpa harus mengalokasikan thread pool baru, memanfaatkan pool dispatcher asal.
* D) Menghapus alokasi heap frame kelanjutan (*continuation allocation*).

---

### Kunci Jawaban & Penjelasan Singkat

* **Q1: C** — Runtime Kotlin melepaskan thread kembali ke pool; Continuation disimpan di memory dan dijadwalkan ulang oleh timer dispatcher.
* **Q2: D** — Disk I/O adalah operasi blocking I/O native yang membutuhkan elastic thread pool (`Dispatchers.IO`) agar tidak menahan worker CPU pool (`Default`).
* **Q3: B** — Karena `catch (e: Exception)` menangkap semua turunan `Exception`, `CancellationException` yang dilempar oleh `delay()` saat scope dibatalkan akan tertangkap dan baris catch dieksekusi.
* **Q4: B** — Melalui transformasi CPS, return type diubah menjadi `Object` dan parameter `Continuation` disuntikkan di akhir signature.
* **Q5: C** — Karakteristik utama `SupervisorJob` adalah isolasi kegagalan: error dari anak tidak merambat ke parent maupun saudaranya.
* **Q6: B** — `coroutineScope` membungkus sub-tree eksekusi. Kegagalan uncaught pada salah satu child langsung membatalkan semua child lainnya di dalam scope tersebut.
* **Q7: B** — `ensureActive()` memverifikasi apakah job masih aktif; jika telah dibatalkan, fungsi langsung melempar `CancellationException`.
* **Q8: C** — `runBlocking` menghentikan thread OS pemanggil hingga blok selesai, yang dapat menyebabkan kelaparan thread (*thread starvation*) pada high-concurrency web server.
* **Q9: B** — `launch` berorientasi *fire-and-forget* (merambat langsung ke atas), sedangkan `async` menahan representasi hasil atau kegagalan di dalam `Deferred`.
* **Q10: C** — `.limitedParallelism` adalah mekanisme manajemen kapasitas yang membatasi eksekusi simultan di atas thread pool yang sudah ada tanpa overhead pembuatan thread native baru.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Resilient Multi-Source Currency Exchange Engine

Bangun sebuah modul mesin pertukaran mata uang (*Forex Aggregator*) mandiri berbasis Kotlin Coroutines dengan spesifikasi arsitektur enterprise berikut:

#### Spesifikasi Kebutuhan

1. **Multi-Provider Querying (Race Condition with Fallback):**
   * Buat service yang mengambil kurs nilai tukar (misal: USD ke IDR) dari 3 Mock API Provider:
     * *Provider Fast-Unreliable:* Rata-rata response time 50ms, namun memiliki kegagalan acak 40% (melempar `IOException`).
     * *Provider Slow-Reliable:* Rata-rata response time 350ms, tingkat keberhasilan 100%.
     * *Provider Stale-Legacy:* Response time 800ms, tingkat keberhasilan 100%.
   * **Target:** Jalankan query secara paralel. Ambil kurs dari provider tercepat yang **sukses**, dan langsung batalkan (*cancel*) query ke provider lainnya yang masih berjalan untuk menghemat resources.

2. **Strict Global SLA (Timeout Throttling):**
   * Total operasi agregasi tidak boleh melebihi batas waktu maksimal **300ms**.
   * Jika tidak ada satupun provider cepat yang sukses dalam 300ms, sistem harus melempar custom exception `CurrencyRateTimeoutException` dan membatalkan seluruh operasi background yang sedang berlangsung.

3. **Concurrency-Safe Audit Logger:**
   * Setiap kali kurs berhasil didapatkan, catat log audit ke background scope (`auditScope`) non-blocking secara asinkron tanpa memperlambat return dari fungsi pemanggil.
   * `auditScope` harus menggunakan `SupervisorJob` agar jika logging gagal, fungsionalitas transaksi utama pertukaran mata uang tidak terdampak sama sekali.

#### Kriteria Pengujian (Checklist Validasi)
* [ ] Menggunakan Structured Concurrency murni (tanpa `GlobalScope` atau thread sleep).
* [ ] Fungsi utama bersifat *Main-Safe* (dapat dipanggil aman dari dispatcher mana pun).
* [ ] Penanganan `CancellationException` dilakukan secara bersih tanpa tertelan di blok `try-catch`.
* [ ] Dilengkapi skenario pengetesan terverifikasi menggunakan `runBlocking` untuk menguji kondisi provider lambat, provider gagal, dan kondisi timeout terlampaui.