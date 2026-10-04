# Bab 01 Module 01: Android Runtime (ART), Ekosistem DEX, dan Siklus Kompilasi Hybrid (AOT/JIT/Baseline Profiles)

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis** siklus hidup bytecode Java/Kotlin dari kompilasi `javac`/`kotlinc`, desugaring D8, obfuscation/shrinking R8, hingga transformasi akhir menjadi Dalvik Executable (`.dex`).
*   **Mendekonstruksi** arsitektur internal Android Runtime (ART), meliputi eksekusi hybrid (Interpreter, Just-In-Time/JIT, Ahead-Of-Time/AOT), *profile-guided compilation*, serta struktur *boot image* (`boot.art`).
*   **Mengimplementasikan dan Mengukur** optimasi *Cold Start* aplikasi menggunakan *Baseline Profiles* dan *Cloud Profiles* via Jetpack Macrobenchmark.
*   **Mendiagnosis** *runtime overhead*, *compilation stalls*, dan proses *class verification failure* pada level AOSP (Android Open Source Project) menggunakan Android Profiler, Perfetto, dan tool CLI ART (`dexdump`, `dexlist`, `oatdump`).

---

### 2. Concept Definition
**Android Runtime (ART)** adalah execution engine tingkat sistem operasi yang mengelola eksekusi aplikasi pada platform Android (menggantikan Dalvik sejak Android 5.0 Lollipop). ART beroperasi dengan mengeksekusi format file **Dalvik Executable (DEX)**—sebuah spesifikasi bytecode berbasis register (*register-based architecture*), berbeda dengan JVM standar yang berbasis stack (*stack-based architecture*). 

Secara modern (Android 7.0 Nougat ke atas), ART mengimplementasikan **Hybrid Compilation Pipeline**: mengombinasikan interpretasi instan, profiling JIT saat runtime, kompilasi AOT latar belakang (*background compilation*) saat perangkat idle/mengisi daya, serta pemanfaatan metadata kompilasi deterministik berbasis **Baseline Profiles** untuk mengeliminasi latensi JIT pada jalur eksekusi kritis (*critical user journey*).

---

### 3. Why It Matters
Pada sistem berbasis JVM desktop atau enterprise server, proses *warm-up* JIT dapat ditoleransi karena server beroperasi dalam rentang waktu berhari-hari hingga berbulan-bulan. Sebaliknya, pada komputasi mobile:
1.  **Cold Start Latency**: Pengguna menuntut aplikasi interaktif dalam <500ms. JIT murni menghasilkan lag dan *frame drops* (jank) karena kompilasi bersaing dengan thread UI untuk memperebutkan alokasi core CPU.
2.  **Resource Constraints (Battery & Thermal)**: Eksekusi berulang melalui interpreter memboroskan siklus instruksi CPU per instruksi bytecode, mempercepat penipisan baterai dan memicu *thermal throttling*.
3.  **Storage Footprint**: Kompilasi AOT penuh (seperti era Android 5.0/6.0) memerlukan waktu instalasi masif dan membengkakkan ukuran biner aplikasi di storage hingga 200–300% (file `.oat`/`.odex`).
4.  **Memory Footprint (RAM)**: Kode mesin yang terkompilasi (*native machine code*) dipetakan ke memori virtual (`mmap`), sementara bytecode DEX yang diinterpretasikan memerlukan struktur memori runtime tambahan untuk status eksekusi.

Pemahaman mendalam mengenai arsitektur ini memungkinkan Anda merekayasa *app initialization pipeline* yang lolos metrik Android Vitals (mencegah degradasi ranking di Google Play Store akibat *Excessive Time to Initial Display*).

---

### 4. Architectural What
Ekosistem eksekusi Android terdiri dari sub-komponen utama:

```
[Kotlin/Java Code] 
       │
   (kotlinc/javac)
       ▼
 [JVM Bytecode .class]
       │
    (D8/R8) ─── Desugaring, Shrinking, Optimization
       ▼
 [DEX Bytecode (.dex)]
       │
 (AAPT2 & Signer)
       ▼
   APK / AAB
       │ (Install via Package Manager Service)
       ▼
 ┌────────────────────────────────────────────────────────┐
 │                     ART ENGINE                         │
 │                                                        │
 │  ┌──────────────┐     ┌──────────────┐                 │
 │  │ Interpreter  │────▶│ JIT Compiler │                 │
 │  └──────┬───────┘     └──────┬───────┘                 │
 │         │ (Hot Code)         │ (Machine Code)          │
 │         ▼                    ▼                         │
 │     Profiles ──────────▶ JIT Code Cache                │
 │        │                                               │
 │        ▼                                               │
 │   art_apex/dex2oat                                     │
 │        │ (Background Compilation)                      │
 │        ▼                                               │
 │   AOT Artifacts (.odex / .vdex)                        │
 └────────────────────────────────────────────────────────┘
```

*   **D8 / R8 Compiler**: 
    *   **D8**: Dexer modern yang mengubah `.class` menjadi `.dex`, menangani *core library desugaring* (memungkinkan API Java 8+ berjalan di Android versi lama).
    *   **R8**: Pengganti ProGuard, mengintegrasikan shrinker, optimizer, obfuscator, dan dexer dalam satu pass tree-shaking terpadu.
*   **Format DEX vs. Java Bytecode**:
    *   Java bytecode menggunakan arsitektur *stack-based* (operasi `push`/`pop`).
    *   DEX menggunakan arsitektur *register-based* dengan register virtual 32-bit/64-bit yang memetakan langsung ke register fisik CPU arsitektur ARM/x86, mereduksi instruksi eksekusi total hingga 30-40%.
*   **Artifacts Eksekusi**:
    *   `.dex`: File Dalvik Executable terkompresi dalam APK.
    *   `.vdex`: Berisi verifikasi DEX yang tervalidasi untuk mempercepat kompilasi berikutnya tanpa perlu re-verifikasi.
    *   `.odex` / `.oat`: File format ELF (*Executable and Linkable Format*) yang membungkus kode mesin native hasil kompilasi AOT untuk instruksi target (ARM64/x86_64).
    *   `.art`: Alokasi *heap image* yang dipetakan langsung ke memori untuk objek-objek kelas kritis guna menghindari parsing runtime.

---

### 5. How It Works
Siklus kompilasi dan eksekusi modern pada level OS mengikuti pipeline transisional berikut:

1.  **Fase Instalasi (Install Time)**:
    *   Package Manager Service (`PMS`) mengekstrak APK.
    *   Jika aplikasi menyertakan `baseline.prof` (dari pustaka Jetpack Profile Installer), utility `dex2oat` mentranslasikan metode yang ditandai dalam profil tersebut menjadi kode mesin native secara AOT menghasilkan file `.odex`/`.vdex`.
    *   Tanpa profile, metode tetap berada dalam bentuk `.dex` murni tanpa AOT berat untuk menjaga waktu instalasi tetap instan.

2.  **Fase Eksekusi Pertama (First Launch / Cold Execution)**:
    *   Zygote memanggil `fork()` untuk membuat instance proses Linux baru bagi aplikasi.
    *   Metode yang belum di-AOT akan dijalankan langsung oleh **Interpreter**.
    *   Interpreter memverifikasi instruksi kelas via verifier internal ART.

3.  **Fase Deteksi Hot Method & JIT (Runtime Compilation)**:
    *   ART memelihara counter eksekusi pada setiap metode.
    *   Ketika counter metode melampaui ambang batas tertentu (menjadi *hot code*), **JIT Compiler** mengeksekusinya di thread terpisah (`Jit thread pool`).
    *   Hasil kompilasi mesin disimpan di **JIT Code Cache** dalam RAM. Pemanggilan berikutnya langsung melompat ke alamat memori instruksi mesin tersebut.

4.  **Fase Profiling (Profile Generation)**:
    *   ART memantau metode dan kelas yang sering dimuat dan menyimpannya ke storage internal aplikasi sebagai file profil runtime (`/data/misc/profiles/cur/0/<package_name>/primary.prof`).

5.  **Fase Pemeliharaan Latar Belakang (Dexopt / Background Optimization)**:
    *   Ketika perangkat dalam kondisi **Idle** (layar mati) dan terhubung ke **Pengisi Daya** (charging), JobScheduler sistem memicu job pemeliharaan: `BackgroundDexoptJob`.
    *   Job ini memanggil `dex2oat` bersama argumen `--compiler-filter=speed-profile` menggunakan file `.prof` yang terakumulasi.
    *   Hasilnya adalah biner AOT baru yang menggantikan kode interpretasi untuk peluncuran aplikasi selanjutnya.

---

### 6. System Architecture Diagram

Berikut visualisasi interaksi subsistem ART, memori, dan storage:

```
[ AOSP OS Layer: Runtime Execution & Storage Topology ]

 +-----------------------------------------------------------------------------------+
 | Linux Process Memory Space (Per-Application)                                      |
 |                                                                                   |
 |  +-----------------------+     +------------------------+                         |
 |  | Dalvik Heap (Zygote)  |     | ART JIT Code Cache     |                         |
 |  | Objects, Arrays       |     | (RWX Memory Pages)     |                         |
 |  +-----------------------+     +------------------------+                         |
 |              ▲                             ▲                                      |
 |              │                             │ Emit Compiled Code                   |
 |  +-----------┴-----------------------------┴-----------------------------------+  |
 |  |                       ART Core Engine (libart.so)                          |  |
 |  |                                                                             |  |
 |  |  +--------------------+        Threshold Exceeded      +-----------------+  |  |
 |  |  |    Interpreter     | ─────────────────────────────▶ |  JIT Compiler   |  |  |
 |  |  |  (mterp execution) | ◀────────────────────────────  |  (vixl backend) |  |  |
 |  |  +--------------------+   Deoptimization Event         +-----------------+  |  |
 |  +-----------------------------------------------------------------------------+  |
 |              ▲                             ▲                                      |
 |              │ mmap (.dex)                 │ mmap Native (.odex / .oat)           |
 +--------------┼─────────────────────────────┼--------------------------------------+
                │                             │
 +--------------┼─────────────────────────────┼--------------------------------------+
 | Storage Subsystem (/data/app/ & /data/dalvik-cache/)                              |
 |                                                                                   |
 |  +------------------+    +-------------------+    +----------------------------+  |
 |  |   base.apk       |    |   base.vdex       |    |   base.odex (ELF)          |  |
 |  |  (Contains .dex) |    |  (Verified Dex)   |    |  (AOT Native Instructions) |  |
 |  +------------------+    +-------------------+    +----------------------------+  |
 |                                                            ▲                      |
 |                                                            │ Compile Output       |
 |                         +-------------------------+        │                      |
 |                         |        dex2oat          |────────┘                      |
 |                         | (ART Compiler Daemon)   |                               |
 |                         +-------------------------+                               |
 |                                    ▲                                              |
 |                                    │ Uses Profile                                 |
 |                         +-------------------------+                               |
 |                         |    primary.prof         |                               |
 |                         | (From JIT/Baseline Prof)|                               |
 |                         +-------------------------+                               |
 +-----------------------------------------------------------------------------------+
```

---

### 7. Mental Model / Analogies
Bayangkan mengoperasikan sebuah restoran global dengan resep masakan asing:
*   **Java/Kotlin Source Code**: Konsep resep dalam bahasa konseptual koki.
*   **DEX Bytecode**: Resep terstandarisasi ringkas yang ditulis dalam instruksi ringkas modular (*register-based notation*).
*   **Interpreter**: Seorang asisten koki yang membaca resep baris demi baris menggunakan kamus manual. Progres lambat, namun persiapan awal tidak butuh waktu persiapan (*instant startup*).
*   **JIT (Just-In-Time)**: Ketika asisten melihat resep menu tertentu dipesan 50 kali dalam satu jam, asisten mencatat instruksi memasak langsung di dinding dapur menggunakan bahasa gerak tubuh instan (bahasa mesin). Kecepatan melonjak drastis, tetapi ada gangguan fokus saat mencatat resep ke dinding.
*   **Baseline Profiles**: Anda membawa daftar "10 menu terpopuler" yang sudah disiapkan oleh koki utama sebelum restoran dibuka.
*   **AOT (dex2oat Background)**: Pada malam hari setelah restoran tutup, staf dapur menghafal 10 menu tersebut di luar kepala hingga ke level memori otot (kompilasi kode native ARM). Esok harinya, menu tersebut dimasak seketika tanpa perlu membaca resep sama sekali.

---

### 8. Minimal Reproducible Example
Pemeriksaan struktur bytecode DEX dan ART profiling secara langsung via Android Debug Bridge (ADB).

Buat file sumber minimal, lalu amati transformasinya menggunakan toolchain command line:

```bash
# 1. Tulis kelas Kotlin/Java sederhana
cat << 'EOF' > StartupSample.java
public class StartupSample {
    public static void main(String[] args) {
        int x = 10;
        int y = 20;
        int z = compute(x, y);
        System.out.println("Result: " + z);
    }

    private static int compute(int a, int b) {
        return a * b + 42;
    }
}
EOF

# 2. Kompilasi ke JVM Bytecode
javac -source 11 -target 11 StartupSample.java

# 3. Konversi ke Android DEX menggunakan tool D8 (Path disesuaikan dengan Android SDK)
$ANDROID_HOME/build-tools/34.0.0/d8 StartupSample.class --output ./output_dex/

# 4. Bongkar (Disassemble) DEX Bytecode untuk melihat instruksi register
$ANDROID_HOME/build-tools/34.0.0/dexdump -d ./output_dex/classes.dex
```

Output representasi Register-based bytecode pada metode `compute`:
```text
  Virtual methods   -
  Direct methods    -
    #1              : (in LStartupSample;)
      name          : 'compute'
      type          : '(II)I'
      access        : 0x000a (PRIVATE STATIC)
      code          -
      registers     : 3
      ins           : 2
      outs          : 0
      insns size    : 4 16-bit code units
00018c: [00018c] mul-int v0, v1, v2           # Mengalikan register v1 dan v2, simpan di v0
00018e: [00018e] add-int/lit8 v0, v0, #int 42 # Tambah konstanta 42 ke v0, simpan di v0
000190: [000190] return v0                    # Return nilai dari register v0
```

*Perhatikan bahwa tidak ada instruksi `push` atau `pop` seperti pada stack JVM; semua komputasi terjadi langsung antar register virtual (`v0`, `v1`, `v2`).*

---

### 9. Step-by-Step Implementation Walkthrough

Mengonfigurasi dan memvalidasi siklus kompilasi secara terprogram pada target Android:

#### Langkah 1: Paksa Reset Profil Kompilasi Aplikasi
Jalankan perintah adb untuk menghapus artefak kompilasi aplikasi Anda untuk simulasi cold start terburuk:
```bash
# Reset status kompilasi ke interpreter murni
adb shell cmd package compile --reset com.example.productionapp
```

#### Langkah 2: Inspeksi Status Kompilasi Saat Ini
Verifikasi bahwa filter kompilasi telah kembali ke `verify` atau `quicken`:
```bash
adb shell dumpsys package com.example.productionapp | grep -A 3 "dexopt"
```
*Output target:*
```text
[com.example.productionapp]
  arm64: [status=verify] [reason=unknown]
```

#### Langkah 3: Eksekusi Peluncuran dan Agregasi JIT Profiling
Buka aplikasi beberapa kali untuk mengumpulkan trace metode yang sering digunakan:
```bash
adb shell monkey -p com.example.productionapp -c android.intent.category.LAUNCHER 1
# Tunggu interaksi, lalu paksa ART mendump memory-profile ke disk:
adb shell kill -SIGUSR1 $(adb shell pidof com.example.productionapp)
```

#### Langkah 4: Picu Kompilasi AOT Background Berbasis Profil
Paksa Android menjalankan task background optimization secara manual menggunakan file profil yang baru diekstraksi:
```bash
adb shell cmd package compile -m speed-profile -f com.example.productionapp
```

#### Langkah 5: Evaluasi Hasil Perubahan Filter
Cek kembali status dexopt:
```bash
adb shell dumpsys package com.example.productionapp | grep -A 3 "dexopt"
```
*Output target sekarang:*
```text
[com.example.productionapp]
  arm64: [status=speed-profile] [reason=bg-dexopt]
```

---

### 10. Practical Real-World Example
Mengimplementasikan **Baseline Profiles** berbasis modul Jetpack Macrobenchmark pada sistem build Android enterprise untuk mengeliminasi latensi interpretasi kode startup (Cold Start Optimization).

#### 1. Setup Gradle Configuration
Pada `app/build.gradle.kts`:
```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.androidx.baselineprofile)
}

android {
    compileSdk = 34

    defaultConfig {
        applicationId = "com.enterprise.app"
        minSdk = 26
        targetSdk = 34
        // ...
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

dependencies {
    // Memberikan API installer runtime agar APK otomatis membaca profile tanpa menunggu OS Idle
    implementation(libs.androidx.profileinstaller)
}
```

#### 2. Generator Test pada Module Macrobenchmark
Pada direktori module terpisah `:baselineprofile`:
```kotlin
package com.enterprise.benchmark

import androidx.benchmark.macro.junit4.BaselineProfileRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
@LargeTest
class GenerateBaselineProfile {

    @get:Rule
    val baselineProfileRule = BaselineProfileRule()

    @Test
    fun generateStartupAndCriticalUserJourneyProfile() {
        baselineProfileRule.collect(
            packageName = "com.enterprise.app",
            // Android 13+ mendukung pengoptimalan runtime berbasis multi-package profile
            maxIterations = 10,
            stableIterations = 3,
            includeInStartupProfile = true
        ) {
            // Jalur 1: Cold Startup
            pressHome()
            startActivityAndWait()

            // Jalur 2: Navigasi Kritis (Critical User Journey)
            // Simulasikan interaksi UI pengguna yang wajib terbebas dari Jank (JIT stall)
            device.waitForIdle()
        }
    }
}
```

#### 3. Rules Obfuscation Protection
Tambahkan ke `app/proguard-rules.pro` untuk mencegah R8 merusak class profile metadata:
```proguard
# Menjaga file descriptor DEX profileinstaller
-keep class androidx.profileinstaller.** { *; }
-dontwarn androidx.profileinstaller.**
```

---

### 11. Implementation Deep Dive
Mari bedah metadata biner Baseline Profiles (`baseline-prof.txt`) yang dikemas ke dalam APK di folder `assets/dexopt/baseline.prof`.

Bentuk teks dari file profil sebelum dikompilasi oleh `profgen`:
```text
# Flags:
# H = Hot Method (JIT diprioritaskan)
# S = Startup Method (Dimuat saat startup awal)
# P = Post-Startup Method

HSPLcom/enterprise/app/ui/MainActivity;->onCreate(Landroid/os/Bundle;)V
HSPLcom/enterprise/app/di/NetworkModule;->provideOkHttpClient()Lokhttp3/OkHttpClient;
Lcom/enterprise/app/model/UserAccount;
```

Ketika installer memasang aplikasi, utilitas `profgen` memvalidasi signature checksum file DEX aplikasi terhadap signature profil:
*   Jika APK dimodifikasi tanpa meng-generate ulang baseline profile, *checksum mismatch* terjadi.
*   ART akan mengabaikan profil sepenuhnya (`STATUS_DEX_METADATA_MISMATCH`) dan aplikasi turun kembali ke mode **Interpreter Murni**.

Struktur biner file `.prof` yang diparsing internal ART:
```
+-----------------------------------------------------------+
| Magic Number (4 Bytes) : "pro\0"                          |
+-----------------------------------------------------------+
| Version (4 Bytes)      : "015\0" (Tergantung versi ART)   |
+-----------------------------------------------------------+
| Number of Dex Files    : uint32                           |
+-----------------------------------------------------------+
| Per Dex Metadata:                                         |
|  - Profile Key Length  : uint16                           |
|  - Profile Key (URI)   : "base.apk!classes.dex"           |
|  - Dex Checksum        : uint32                           |
|  - Number of Methods   : uint32                           |
|  - Method Index Bitset : [Flags (H, S, P) | Method IDs...] |
|  - Class Index Array   : [Type IDs...]                    |
+-----------------------------------------------------------+
```

---

### 12. Edge Cases, Failure Modes & Pitfalls

#### 1. Verifier Rejection & Class Loader Mismatch
*   **Kasus Gagal**: Memuat class saat runtime via custom dynamic class loader tanpa memberitahu skema kompilasi ART.
*   **Dampak**: ART mendeteksi dependensi class hilang pada tahap verifikasi AOT. Metode fallback ke interpreted execution seketika, menghasilkan *compilation stall* ratusan milidetik.
*   **Mitigasi**: Pastikan seluruh skema modularisasi/dynamic feature didaftarkan melalui `BaseDexClassLoader` yang valid agar metadata terlihat oleh `dexopt`.

#### 2. Baseline Profile Checksum Invalidations
*   **Kasus Gagal**: Baseline profile di-*generate* pada branch CI `staging`, namun build `release` memiliki dependency patch level yang berbeda atau optimasi R8 ekstra.
*   **Dampak**: Dex checksum mismatch. ART membuang profile. Terjadi degradasi Cold Start hingga 40% tanpa disadari tim engineer.

#### 3. JIT Code Cache Exhaustion (Memory Pressure)
*   **Kasus Gagal**: Aplikasi memiliki basis kode raksasa non-modular yang memaksa pemanggilan ribuan class dalam rentang waktu singkat.
*   **Dampak**: Buffer JIT code cache (biasanya dialokasikan terbatas, default ~4MB - 8MB tergantung RAM device) mengalami overflow. Terjadi siklus eliminasi instruksi kompilasi native (*code thrashing*), memaksa kompilasi ulang yang memakan CPU secara ekstrem.

---

### 13. Architectural Trade-offs & Analysis

Keputusan arsitektur eksekusi pada level Android OS merepresentasikan pertukaran parameter teknis yang ketat:

| Strategi Kompilasi | Waktu Instalasi | Ukuran Storage (Disk Footprint) | Latensi Cold Start (Initial Display) | Efisiensi Baterai (CPU Draw) |
| :--- | :--- | :--- | :--- | :--- |
| **Interpreter Only** | Instan (< 1s) | Sangat Ringan (Hanya `.dex`) | Sangat Buruk (High Latency) | Sangat Buruk (Instruksi konstan) |
| **Full AOT (`speed`)**| Sangat Lambat (Bisa bermenit-menit) | Sangat Boros (Besar file ELF native 200-300%) | Optimal (Tertinggi) | Optimal (Kode mesin langsung) |
| **Pure JIT** | Cepat | Ringan | Menengah (Lag pada initial phase) | Menengah (Siklus CPU untuk compil JIT) |
| **Hybrid + Baseline Profiles** | Cepat | Efisien (Hanya jalur kritis yang di-AOT) | Mendekati Full AOT pada Startup Path | Sangat Baik (Beban CPU berkurang di jalur awal) |

*Kesimpulan Arsitektur*: Modern ART mengorbankan kesederhanaan *compilation toolchain* demi menyeimbangkan dua dimensi yang saling berlawanan: kecepatan instalasi dan latensi peluncuran awal.

---

### 14. Security & Hardening Implications

DEX dan eksekusi ART adalah vektor serangan utama pada platform Android:

1.  **DEX In-Memory Dumping**:
    *   Karena ART harus memetakan file DEX ke memori virtual (`mmap`), attacker dengan akses Frida/Xposed dapat mendump memory ranges yang memiliki header dex `0x64 0x65 0x78 0x0a` (`dex\n`) untuk membongkar aplikasi terenkripsi.
    *   *Hardening*: Terapkan R8 full mode dengan aggressively strip attribute name, implementasikan teknik dynamic proxy checks, dan hapus debugging symbols via NDK strip.
2.  **App Sandbox Boundaries**:
    *   Kode hasil kompilasi AOT (`.odex`) disimpan di bawah direktori yang dilindungi sandboxing Linux UID: `/data/app/<app-id>/oat/`. File ini dimiliki oleh user `system` dan grup internal aplikasi untuk membatasi injeksi kode arbitrary pada file ELF.
3.  **W^X (Write XOR Execute) Memory Pages**:
    *   ART JIT Compiler secara berkala memvalidasi memory security policy. Halaman memori tidak boleh memiliki izin Read-Write-Execute bersamaan. Ketika JIT menulis instruksi mesin, halaman diset sebagai `RW-`. Selesai ditulis, permission dimutasi via `mprotect()` menjadi `R-X`.

---

### 15. Testing & Verification Strategies

Untuk memvalidasi bahwa performa eksekusi aplikasi optimal pada level ART, gunakan Jetpack Macrobenchmark dengan skenario filter kompilasi terkontrol.

```kotlin
package com.enterprise.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class StartupBenchmark {
    @get:Rule
    val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun startupNoCompilation() = startup(CompilationMode.None())

    @Test
    fun startupBaselineProfiles() = startup(
        CompilationMode.Partial(
            baselineProfileMode = androidx.benchmark.macro.BaselineProfileMode.Require
        )
    )

    @Test
    fun startupFullAot() = startup(CompilationMode.Full())

    private fun startup(compilationMode: CompilationMode) =
        benchmarkRule.measureRepeated(
            packageName = "com.enterprise.app",
            metrics = listOf(StartupTimingMetric()),
            compilationMode = compilationMode,
            iterations = 5,
            startupMode = StartupMode.COLD
        ) {
            pressHome()
            startActivityAndWait()
        }
}
```

Jalankan pengujian via terminal untuk mengekstrak metrik kuantitatif:
```bash
./gradlew :benchmark:connectedCheck -P android.testInstrumentationRunnerArguments.class=com.enterprise.benchmark.StartupBenchmark
```

Bandingkan metrik `timeToInitialDisplayMs` di antara ketiga mode tersebut untuk memastikan implementasi Profile berfungsi signifikan.

---

### 16. Observability, Telemetry & Diagnostics

Untuk mendiagnosis masalah runtime secara mendalam, gunakan alat tracing performa level OS:

#### 1. Perfetto Tracing
Rekam trace system untuk melihat aktivitas kompilasi JIT saat runtime:
```bash
# Record trace selama 10 detik
adb shell perfetto \
  -c - --txt \
  -o /data/misc/perfetto-traces/trace.perfetto-trace <<'EOF'
buffers: {
    size_kb: 63488
    fill_policy: RING_BUFFER
}
data_sources: {
    config {
        name: "linux.ftrace"
        ftrace_config {
            ftrace_events: "sched_switch"
            ftrace_events: "power/cpu_frequency"
            atrace_categories: "dalvik"
            atrace_apps: "com.enterprise.app"
        }
    }
}
duration_ms: 10000
EOF

# Tarik trace file
adb pull /data/misc/perfetto-traces/trace.perfetto-trace .
```
Buka file pada [ui.perfetto.dev](https://ui.perfetto.dev). Amati slice thread:
*   Cari track bernama **`JIT thread pool`**.
*   Jika track ini aktif terus-menerus selama frame UI digambar, ini indikasi bahwa *Baseline Profiles* Anda tidak meng-cover kelas yang sedang dieksekusi, memicu CPU contention.

#### 2. ART Diagnostics Runtime Dump
```bash
# Dump metrik internal ART ke logcat
adb shell cmd package dump com.enterprise.app
```

---

### 17. Best Practices & Design Principles

#### DO:
*   **Otomatisasi Baseline Profile Generation pada CI/CD**: Jadwalkan pengujian macrobenchmark pada physical device farm setiap kali ada release major.
*   **R8 Optimization Full Mode**: Aktifkan `android.enableR8.fullMode=true` di `gradle.properties` untuk mereduksi ukuran DEX secara agresif sehingga parsing memory lebih cepat.
*   **Terapkan Lazy Initialization**: Jangan menginisialisasi framework besar (misal Firebase, Image Loaders, DI Graphs) di `Application.onCreate()` kecuali benar-benar dibutuhkan sebelum frame pertama digambar.

#### DON'T:
*   **Hindari Reflection di Critical Path Startup**: Menggunakan Java Reflection mencegah AOT inlining compiler melakukan optimasi langsung pada call-site, memicu runtime lookup via symbol tables yang lambat.
*   **Jangan Membuat DEX Multi-file Tidak Seimbang**: Hindari mendistribusikan class dependensi startup ke dalam secondary DEX (`classes2.dex`, `classes3.dex`) secara acak. Letakkan semua critical startup class di `classes.dex` utama via R8 main-dex-rules.

---

### 18. Anti-Patterns & Code Smells

#### 1. The "Kitchen Sink" Application Class
```kotlin
// BAD: Semua SDK diinisialisasi secara sinkron pada Application.onCreate()
class AntiPatternApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        initAnalytics()      // Butuh disk I/O & JIT class loading
        initCrashlytics()    // Butuh IPC initialization
        initPushNotifications() // Membaca keystore
        initDatabaseSync()   // Berat pada ART ClassLoader
    }
}
```
*Dampak*: Ratusan class dipaksa masuk ke interpreter secara instan sebelum Choreographer dapat menggambar frame pertama.

#### 2. Primitive Boxing Storms di Background Loop
```kotlin
// BAD: Memicu alokasi masif pada Heap, mempercepat kerja ART Garbage Collector (GC)
fun computeTelemetry(data: List<Int>) {
    var sum: Long = 0L // Objek Long
    for (i in 0 until 1_000_000) {
        sum += i // Boxing & Unboxing konstan
    }
}
```
*Dampak*: ART Runtime memicu `GC concurrent copying (CC)`, membekukan thread eksekusi (*stop-the-world pauses* pendek) yang merusak konsistensi frame rate (jank).

---

### 19. Self-Assessment & Hands-on Challenge

#### Hands-on Challenge:
1.  Ambil aplikasi produksi Anda atau buat project kompleks dengan minimal 3 activity, implementasi database Room, dan network client Retrofit.
2.  Bongkar APK rilis menggunakan `apkanalyzer` atau CLI `dexdump`. Hitung jumlah total metode dan distribusi class di antara file-file DEX (`classes.dex`, `classes2.dex`).
3.  Jalankan command reset profil ART pada emulator/device target. Rekam metrik Cold Start menggunakan Jetpack Macrobenchmark tanpa Baseline Profiles.
4.  Generate file `baseline-prof.txt` yang valid, integrasikan kembali ke build release, dan buktikan secara empiris via Macrobenchmark bahwa ada penurunan `timeToInitialDisplayMs` minimal sebesar **15%**.

#### Kriteria Keberhasilan:
*   Laporan perbandingan boxplot Macrobenchmark (`CompilationMode.None` vs `CompilationMode.Partial`) terdokumentasi.
*   Log `dexopt` menunjukkan status `[status=speed-profile]` pada physical target device.
*   Trace Perfetto membuktikan tidak ada aktivitas slice `Compiling...` pada JIT Thread pool selama fase peluncuran splash screen menuju home screen.

---

### 20. Further Reading & Canonical References

*   **AOSP Documentation**: *Android Runtime (ART) Architecture and Compilation Formats* — [source.android.com/devices/tech/dalvik](https://source.android.com/devices/tech/dalvik)
*   **Android Open Source Project**: *dex2oat Source Code* — `platform/art/dex2oat/dex2oat.cc`
*   **Dalvik Executable Specification**: Format byte level DEX — [source.android.com/devices/tech/dalvik/dex-format](https://source.android.com/devices/tech/dalvik/dex-format)
*   **Android Developers Guide**: *Baseline Profiles Architecture & Implementation* — [developer.android.com/topic/performance/baselineprofiles/overview](https://developer.android.com/topic/performance/baselineprofiles/overview)
*   **Google I/O Technical Deep Dive**: *AOT, JIT, and Cloud Profiles in Modern Android Runtime* (Technical Sessions).