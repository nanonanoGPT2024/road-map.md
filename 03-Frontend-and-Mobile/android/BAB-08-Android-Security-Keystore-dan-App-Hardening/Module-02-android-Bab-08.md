# BAB 08: Android Security, Keystore, dan App Hardening
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda ditargetkan untuk dapat:
- Merancang dan mengimplementasikan arsitektur kriptografi enterprise pada Android menggunakan **Android Keystore System** dengan isolasi hardware (**TEE** dan **StrongBox Keymaster/KeyMint**).
- Mengonfigurasi kunci kriptografi berbasis biometrik (`BiometricPrompt`) menggunakan `CryptoObject` untuk menjamin otentikasi hardware-enforced.
- Melakukan verifikasi integritas perangkat dan aplikasi secara *end-to-end* melalui **Play Integrity API** dan **Key Attestation** (ASN.1 parser & certificate chain verification).
- Membangun sistem pertahanan aplikasi berlapis (*Defense-in-Depth*) melalui **Native Code Hardening (NDK C++)**, deteksi dynamic instrumentation (Frida, Xposed), anti-debugging (`ptrace`), dan deteksi root/tampering.
- Mengonfigurasi proteksi jaringan tingkat lanjut dengan dynamic Certificate Pinning, Cleartext Traffic Prevention, dan Network Security Config.
- Mengoptimalkan obfuscation rules pada **R8/ProGuard** untuk mencegah reverse-engineering kelas enterprise.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Android Internals**: Memahami lifecycle Android, IPC/Binder, Android Runtime (ART), Zygote process, dan Hardware Abstraction Layer (HAL).
- **Core Cryptography**: Konsep Symmetric Encryption (AES-GCM), Asymmetric Encryption (RSA, ECDSA), Message Authentication Code (HMAC), Digital Signature, X.509 Certificate, and Public Key Infrastructure (PKI).
- **Advanced Kotlin & Modern Android**: Kotlin Coroutines, Flow, Dagger/Hilt, Jetpack Lifecycle.
- **Android NDK Fundamentals**: Sintaks dasar C/C++, CMake, POSIX system calls, dan Java Native Interface (JNI).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Android Keystore Internals & Hardware Backing
Sistem Android Keystore tidak mengekspos material kunci (*raw key bytes*) ke memori proses aplikasi (*untrusted userspace*). Kunci dibuat, disimpan, dan digunakan langsung di dalam hardware terisolasi.

```
+-----------------------------------------------------------------------+
| Untrusted Domain (Android OS / Rich Execution Environment - REE)      |
|                                                                       |
|  +--------------------+       +------------------------------------+  |
|  |   App Process      |  JNI  |  Android Framework                 |  |
|  |  (Kotlin / Java)   | <---> |  (android.security.keystore.*)     |  |
|  +--------------------+       +------------------------------------+  |
|            |                                    |                     |
|            +------------------+                 | IPC / Binder        |
|                               |                 v                     |
|                               |       +--------------------+          |
|                               +-----> |   keystore2 Daemon |          |
|                                       +--------------------+          |
+--------------------------------------------------|--------------------+
                                                   | HAL (HIDL/Aidl)
+--------------------------------------------------v--------------------+
| Hardware Isolated Domain                                              |
|                                                                       |
|  +---------------------------------+  +----------------------------+  |
|  | Trusted Execution Env (TEE)     |  | StrongBox KeyMint (SE)     |  |
|  | - ARM TrustZone                 |  | - Dedicated Microchip      |  |
|  | - KeyMaster / KeyMint HAL       |  |   (e.g., Titan M2)         |  |
|  | - Memory & CPU isolation        |  | - Tamper-resistant CPU/RAM |  |
|  | - High throughput crypto        |  | - Ultra-secure, low I/O    |  |
|  +---------------------------------+  +----------------------------+  |
+-----------------------------------------------------------------------+
```

1. **Keystore2 Daemon (`keystore2`)**:
   Diperkenalkan sejak Android 12, ditulis dalam bahasa Rust untuk menjamin memory-safety. Bertindak sebagai *broker* IPC Binder yang memisahkan aplikasi dari implementasi HAL kriptografi tingkat rendah. Mengelola namespace kunci, otorisasi per-UID, metadata, dan rate-limiting.
2. **KeyMint (sebelumnya KeyMaster)**:
   Spesifikasi HAL yang menghubungkan OS dengan *secure execution environment*. KeyMint memproses operasi kriptografi (*generate*, *import*, *encrypt*, *decrypt*, *sign*, *verify*).
3. **Hardware Isolation**:
   - **TEE (Trusted Execution Environment)**: Berjalan pada prosesor utama menggunakan partisi hardware seperti ARM TrustZone. Memiliki OS mikro sendiri (seperti Trusty OS, Qualcomm QSEE).
   - **StrongBox**: Modul perangkat keras terpisah secara fisik (*Secure Element* - SE) dengan CPU independen, memori tersendiri, dan deteksi fisik anti-tamper (contoh: chip Titan M2 pada Google Pixel). Operasi kriptografinya jauh lebih aman terhadap serangan *side-channel* dan *hardware probing*, namun memiliki throughput komputasi lebih rendah dibandingkan TEE.

#### 3.2 Key Attestation
Key Attestation memverifikasi bahwa pasangan kunci yang dibuat benar-benar didukung oleh hardware tersertifikasi (TEE atau StrongBox) dan properties kunci (seperti otentikasi biometrik) tidak dimanipulasi oleh OS yang telah di-*compromise* (rooted/modified).
- Hardware menyertakan sertifikat X.509 berantai (*certificate chain*) hingga ke *Google Root CA*.
- *Attestation Certificate* memuat ekstensi kustom (OID `1.3.6.1.4.1.11129.2.1.17`) bertipe ASN.1 data structure yang menyimpan:
  - Software digest / OS version / Security Patch level.
  - Hardware vs Software security level.
  - Challenge acak yang dikirim backend untuk mencegah *replay attack*.

#### 3.3 Dynamic Instrumentation Protection (Anti-Frida & Anti-Ptrace)
Frida bekerja dengan menginjeksi *shared library* (`gadget.so`) atau terhubung melalui `frida-server` menggunakan fasilitas OS `ptrace` (process trace) dan manipulasi `/proc/self/maps` serta `/proc/self/status`.
- **Ptrace Protection**: Sebuah proses Linux hanya dapat di-attach oleh satu tracer. Memanggil `ptrace(PTRACE_TRACEME, 0, 1, 0)` secara native mencegah debugger eksternal meng-attach dirinya ke proses aplikasi.
- **Memory Scanning**: Menelusuri file descriptor virtual `/proc/self/maps` untuk mendeteksi artefak library Frida, Cydia Substrate, atau Xposed framework.

---

### 4. Why & What

| Fitur / Mekanisme | Mengapa Dibutuhkan (Why) | Apa Karakteristik Utamanya (What) |
| :--- | :--- | :--- |
| **Hardware-Backed Keystore** | Menghindari ekstraksi *private key* dari RAM/Heap Dump bahkan jika OS di-root. | Operasi kriptografis dijalankan di dalam TEE/StrongBox SE; kunci private tidak pernah keluar ke memory space aplikasi. |
| **Biometric `CryptoObject`** | Memastikan transaksi kritis hanya bisa dieksekusi jika otentikasi biometrik lokal valid seketika. | Membuka operasi kriptografi kunci Keystore hanya selama durasi otentikasi biometrik aktif (`setUserAuthenticationRequired(true)`). |
| **Key Attestation** | Mencegah perangkat rooted mengklaim bahwa mereka menggunakan hardware secure element padahal menggunakan software keystore palsu. | Verifikasi rantai sertifikat X.509 dari TEE/StrongBox yang ditandatangani root Google langsung di sisi backend. |
| **NDK Anti-Hooking & Anti-Debug** | Menahan serangan reverse engineering real-time (Frida dynamic hooking, memory patching). | Proteksi tingkat rendah (C/C++) menggunakan interaksi kernel POSIX yang sulit di-intercept dibanding JVM/ART API. |
| **Play Integrity API** | Memastikan request berasal dari binary aplikasi asli yang didistribusikan Google Play pada perangkat yang lolos validasi CTS/Play Protect. | Token JWT bertanda tangan Google yang divalidasi backend untuk otorisasi akses API enterprise. |

---

### 5. How: Workflow Detail

#### End-to-End Secure Transaction Signing Workflow
Berikut alur eksekusi tanda tangan digital transaksi finansial berbasis Biometrik + KeyStore + Attestation:

```
+-----+             +---------------+        +----------+        +-------------+        +-------------+
| App |             | BiometricMgr  |        | Keystore |        | TEE/KeyMint |        | Backend API |
+-----+             +---------------+        +----------+        +-------------+        +-------------+
   |                        |                      |                    |                      |
   | 1. Init Transaction    |                      |                    |                      |
   |----------------------->|                      |                    |                      |
   |                        | 2. Init Cipher/Sign  |                    |                      |
   |                        |--------------------->|                    |                      |
   |                        |                      | 3. Crypto Init     |                      |
   |                        |                      | (Auth Required)    |                      |
   |                        |                      |------------------->|                      |
   |                        |                      |                    |--+                   |
   |                        |                      |                    |  | Lock Cipher       |
   |                        |                      |                    |<-+ (Unusable state)  |
   |                        |                      | 4. Return Cipher   |                      |
   |                        |                      |<-------------------|                      |
   |                        | 5. Return CryptoObj  |                    |                      |
   |                        |<---------------------|                    |                      |
   | 6. Show Biometric UI   |                      |                    |                      |
   |    with CryptoObject   |                      |                    |                      |
   |<-----------------------|                      |                    |                      |
   |                        |                      |                    |                      |
   | 7. User Scans Finger   |                      |                    |                      |
   |----------------------->|                      |                    |                      |
   |                        | 8. Auth Success      |                    |                      |
   |                        |----+                 |                    |                      |
   |                        |    | Unlock AuthToken|                    |                      |
   |                        |    | via TEE Gatekpr |                    |                      |
   |                        |<---+                 |                    |                      |
   |                        | 9. Perform Sign      |                    |                      |
   |                        |--------------------->|                    |                      |
   |                        |                      | 10. Execute Inside |                      |
   |                        |                      |     Secure HW      |                      |
   |                        |                      |------------------->|                      |
   |                        |                      | 11. Signature Res  |                      |
   |                        |                      |<-------------------|                      |
   |                        | 12. Deliver Payload  |                    |                      |
   |                        |<---------------------|                    |                      |
   | 13. Send Signed TX     |                      |                    |                      |
   |------------------------------------------------------------------------------------------>|
   |                        |                      |                    |                      | 14. Verify PubKey
   |                        |                      |                    |                      |     & Attestation
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Brankas Diplomatik Swiss dengan Dual-Control
Bayangkan **Android Keystore** adalah sebuah brankas baja tahan ledakan di dalam kedutaan besar (**TEE/StrongBox**):
- **Aplikasi (Untrusted OS)** adalah staf kedutaan biasa. Staf tidak pernah tahu kombinasi brankas (*private key*).
- Jika staf ingin menandatangani dokumen (*data signature*), staf memasukkan dokumen melalui celah kecil pada brankas.
- Staf keamanan bersenjata (**Biometric Gatekeeper**) harus memindai sidik jari pejabat yang berwenang sebelum tuas stempel brankas mau mencap dokumen tersebut.
- Dokumen keluar dengan cap resmi, tanpa staf pernah melihat atau menyentuh stempel aslinya secara langsung.
- **Key Attestation** adalah surat sertifikasi dari pabrik brankas yang menyatakan bahwa brankas tersebut memiliki spesifikasi baja militer nomor seri resmi, bukan brankas kardus buatan sendiri.

---

### 7. Implementasi Kode Standar Industri

Berikut adalah implementasi sistem kriptografi dan proteksi hardware berbasis Enterprise.

#### 7.1 Security Keystore Manager (`SecureCryptoEngine.kt`)
Mengelola kunci asimetris berbasis ECDSA (P-256) dengan fallback StrongBox, mewajibkan biometrik, serta memvalidasi status invalidasi saat terjadi registrasi sidik jari baru.

```kotlin
package com.enterprise.security.crypto

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import androidx.biometric.BiometricPrompt
import java.io.IOException
import java.security.*
import java.security.spec.ECGenParameterSpec
import javax.crypto.Cipher
import javax.crypto.NoSuchPaddingException

class SecureCryptoEngine(private val context: Context) {

    companion object {
        private const val ANDROID_KEYSTORE_PROVIDER = "AndroidKeyStore"
        private const val KEY_ALIAS = "ENTERPRISE_TRANSACTION_KEY"
        private const val SIGNATURE_ALGORITHM = "SHA256withECDSA"
    }

    private val keyStore: KeyStore = KeyStore.getInstance(ANDROID_KEYSTORE_PROVIDER).apply {
        load(null)
    }

    /**
     * Memeriksa keberadaan chip StrongBox (Secure Element terisolasi).
     */
    fun hasStrongBoxSupport(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            context.packageManager.hasSystemFeature(PackageManager.FEATURE_STRONGBOX_KEYSTORE)
        } else {
            false
        }
    }

    /**
     * Membuat pasangan kunci Hardware-Backed ECDSA P-256.
     * Menerapkan fallback dari StrongBox ke TEE jika StrongBox tidak tersedia.
     */
    fun generateHardwareBackedKeyPair(challenge: ByteArray): KeyPair {
        val useStrongBox = hasStrongBoxSupport()
        return try {
            buildKeyPair(useStrongBox = useStrongBox, challenge = challenge)
        } catch (e: Exception) {
            if (useStrongBox && Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                // Fallback ke Standard TEE jika StrongBox mengalami resource allocation failure
                buildKeyPair(useStrongBox = false, challenge = challenge)
            } else {
                throw e
            }
        }
    }

    private fun buildKeyPair(useStrongBox: Boolean, challenge: ByteArray): KeyPair {
        val keyPairGenerator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_EC,
            ANDROID_KEYSTORE_PROVIDER
        )

        var builder = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
        )
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            // Memerlukan otentikasi biometrik setiap kali private key digunakan
            .setUserAuthenticationRequired(true)
            // Invalidate kunci jika user mendaftarkan biometrik baru di OS settings
            .setInvalidatedByBiometricEnrollment(true)
            // Attestation challenge untuk validasi keaslian hardware di backend
            .setAttestationChallenge(challenge)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && useStrongBox) {
            builder = builder.setIsStrongBoxBacked(true)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // Membatasi akses kunci hanya untuk BIOMETRIC_STRONG
            builder = builder.setUserAuthenticationParameters(
                0, // 0 = timeout segera habis, memerlukan autentikasi setiap operasi
                KeyProperties.AUTH_BIOMETRIC_STRONG
            )
        }

        keyPairGenerator.initialize(builder.build())
        return keyPairGenerator.generateKeyPair()
    }

    /**
     * Menginisialisasi Signature instance dan membungkusnya ke dalam BiometricPrompt.CryptoObject.
     */
    @Throws(KeyPermanentlyInvalidatedException::class, GeneralSecurityException::class)
    fun createCryptoObject(): BiometricPrompt.CryptoObject {
        val privateKey = keyStore.getKey(KEY_ALIAS, null) as? PrivateKey
            ?: throw KeyStoreException("Private key tidak ditemukan pada Keystore.")

        val signature = Signature.getInstance(SIGNATURE_ALGORITHM).apply {
            initSign(privateKey)
        }
        return BiometricPrompt.CryptoObject(signature)
    }

    /**
     * Mengambil certificate chain untuk dikirimkan ke server demi validasi Key Attestation.
     */
    fun getCertificateChain(): List<java.security.cert.Certificate> {
        return keyStore.getCertificateChain(KEY_ALIAS)?.toList() ?: emptyList()
    }
}
```

#### 7.2 Native Anti-Tampering Engine (NDK C++)
Implementasi C++ untuk memeriksa `ptrace` tracing dan manipulasi Frida direktori memori.

**File: `app/src/main/cpp/anti_tamper.cpp`**
```cpp
#include <jni.h>
#include <string>
#include <unistd.h>
#include <sys/ptrace.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <fstream>
#include <sstream>
#include <android/log.h>

#define TAG "SecurityEngineNative"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, TAG, __VA_ARGS__)

/**
 * Mendeteksi ptrace attachment (debugger / frida tracing).
 * Menggunakan ptrace PTRACE_TRACEME. Jika gagal, berarti proses sedang di-debug.
 */
static bool isDebuggedViaPtrace() {
    if (ptrace(PTRACE_TRACEME, 0, 1, 0) < 0) {
        return true; // Already traced!
    }
    // Detach kembali agar proses berjalan normal
    ptrace(PTRACE_DETACH, 0, 1, 0);
    return false;
}

/**
 * Memeriksa /proc/self/maps untuk keberadaan artefak Frida atau Substrate.
 */
static bool scanProcMapsForHooks() {
    std::ifstream mapsFile("/proc/self/maps");
    if (!mapsFile.is_open()) {
        return true; // Akses diblokir atau anomali lingkungan, anggap berisiko
    }

    std::string line;
    const std::string fridaPatterns[] = {
        "frida-gadget",
        "frida-agent",
        "libfrida",
        "gum-js-loop",
        "linjector"
    };

    while (std::getline(mapsFile, line)) {
        for (const auto& pattern : fridaPatterns) {
            if (line.find(pattern) != std::string::npos) {
                return true; // Frida module ditemukan dalam address space
            }
        }
    }
    return false;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_enterprise_security_tamper_NativeSecurityEngine_performIntegrityCheck(
        JNIEnv* env,
        jobject /* this */) {
    
    if (isDebuggedViaPtrace()) {
        LOGD("CRITICAL: Ptrace Debugger terdeteksi.");
        return JNI_FALSE;
    }

    if (scanProcMapsForHooks()) {
        LOGD("CRITICAL: Injeksi Frida terdeteksi pada virtual memory.");
        return JNI_FALSE;
    }

    return JNI_TRUE;
}
```

#### 7.3 Android Obfuscation & R8 Configuration
**File: `proguard-rules.pro`**
```proguard
# Hardening Aggressive Mode R8
-repackageclasses 'com.enterprise.security.obf'
-allowaccessmodification
-overloadaggressively

# Matikan atribut debugging yang tidak diperlukan di production
-renamesourcefileattribute SourceFile
-keepattributes SourceFile,LineNumberTable
# Strip line number jika ingin proteksi stack trace maksimal (Gunakan mapping retrace backend)
#-keepparameternames

# Pertahankan Security Entry Point NDK
-keepclasseswithmembernames,includedescriptorclasses class com.enterprise.security.tamper.NativeSecurityEngine {
    native <methods>;
}

# Lindungi entity DTO serializable untuk transaksi API
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}

# Hilangkan log Android level debug/verbose di build release
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
}
```

#### 7.4 Network Security Config dengan Certificate Pinning
**File: `res/xml/network_security_config.xml`**
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- Matikan seluruh Cleartext (HTTP biasa) secara global -->
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>

    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.corebank.enterprise.com</domain>
        <pin-set expiration="2026-12-31">
            <!-- SHA-256 SPKI fingerprint pin utama -->
            <pin digest="SHA-256">7HIpactkIAq2Y49orFOOQKurWxmmSFZhBCoQYcRhJ3Y=</pin>
            <!-- Backup pin (Wajib ada untuk mencegah brick saat key rotation) -->
            <pin digest="SHA-256">k2v657xBsOwg11+SZqYQIUp1R6zOMu7c9j9k68qj1vM=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

---

### 8. Real World Case Study: Tier-1 Digital Bank (High-Risk Transaction Flow)

#### Konteks Masalah
Bank digital tier-1 menghadapi serangan terstruktur:
1. Penyerang mengotomatisasi pengiriman dana melalui emulator yang di-root dengan Magisk dan Zygisk.
2. Hooking via Frida digunakan untuk melewati verifikasi biometrik pada layer Java (`BiometricPrompt.AuthenticationCallback.onAuthenticationSucceeded`).
3. Private key aplikasi diekstraksi dari memory heap pada perangkat yang telah dieksploitasi.

#### Solusi Arsitektur
Bank mendesain ulang arsitektur klien dan backend:

```
[Android App]                                             [Core Banking Server]
      |                                                             |
      | 1. Request Transaction Challenge                            |
      |------------------------------------------------------------>|
      | 2. Return Dynamic Nonce (Cryptographic Challenge)           |
      |<------------------------------------------------------------|
      |                                                             |
      | 3. Local Hardware-Protected Operation:                      |
      |    a. Native C++ checks (Anti-Frida/Ptrace)                 |
      |    b. Unlock Hardware-Backed Key via Biometric CryptoObject |
      |    c. Sign Payload + Nonce inside TEE / StrongBox           |
      |    d. Request Google Play Integrity Token                   |
      |                                                             |
      | 4. Submit Signed Transaction Payload +                      |
      |    Attestation Proof + Play Integrity Token                 |
      |------------------------------------------------------------>|
      |                                                             |
      |                                            5. Server-Side Verification:
      |                                               - Validate Nonce (Anti-replay)
      |                                               - Validate Play Integrity via Google API
      |                                               - Verify Signature with stored Attested PubKey
      |                                               - Check Hardware Security Level (TEE/StrongBox)
      |                                               - If invalid: Reject & Freeze Account
      | 6. Transaction Processed & Confirmed                        |
      |<------------------------------------------------------------|
```

1. **Anti-Bypass Biometrik Menggunakan Kriptografi**: Menghapus flag boolean `isSuccess` yang rentan di-hook. Sebagai gantinya, data transaksi ditandatangani menggunakan `CryptoObject` yang terkunci di dalam StrongBox. Jika biometrik di-bypass via memory hooking, private key tidak akan ter-unlock di level hardware TEE/StrongBox, sehingga proses *signature* menghasilkan *runtime error* (`SignatureException`).
2. **Key Attestation Enforcement**: Backend hanya menerima registrasi Public Key jika Certificate Chain-nya terbukti berakar pada *Google Root CA* dan `attestationSecurityLevel` bernilai `TrustedEnvironment` atau `StrongBox`.
3. **Play Integrity Validasi Cloud**: Backend melakukan pertukaran token Play Integrity dengan Google servers untuk memastikan binary digest cocok dan tidak di-repackage.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Konsekuensi / Biaya (Cons) |
| :--- | :--- | :--- |
| **StrongBox KeyStore** | Ketahanan tertinggi terhadap serangan fisik & side-channel; isolasi chip terpisah. | Latensi operasi kriptografi lebih tinggi (30–100ms lebih lambat dibanding TEE); keterbatasan storage slot kunci; tidak didukung di semua perangkat (flagship only). |
| **TEE (ARM TrustZone)** | Kecepatan enkripsi/tanda tangan sangat tinggi; didukung hampir semua perangkat modern. | Secara teoritis lebih rentan terhadap eksploitasi kernel tingkat mikroarsitektur CPU bersama (shared silicon). |
| **Strict Native Anti-Tampering (NDK)** | Sulit dimanipulasi dengan hooking Java tingkat tinggi (Xposed/Frida runtime). | Kompleksitas maintainability meningkat; potensi false-positive pada Custom ROM tertentu; risiko crash (*SIGSEGV*) jika terjadi bug memori. |
| **`setInvalidatedByBiometricEnrollment(true)`** | Menghentikan penyalahgunaan jika seseorang berhasil menambahkan sidik jari baru ke perangkat target. | UX Trade-off: Mengharuskan pengguna re-registrasi/login ulang secara penuh saat mereka menambahkan sidik jari baru secara sah di OS. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal yang Sering Terjadi
1. **Verifikasi Token Play Integrity di Klien**:
   *Fatal*: Memvalidasi Play Integrity token JWT langsung di dalam aplikasi Android. Penyerang cukup memotong logic verifikasi via Frida. Token **harus** dikirim dan didekripsi di backend menggunakan private key API Google Anda.
2. **Reusing Nonce/IV pada Enkripsi AES-GCM**:
   *Fatal*: Menggunakan Static Initialization Vector (IV) pada AES-GCM. Menggunakan IV yang sama dua kali dengan AES-GCM mengekspos Galois Hash key, merusak *confidentiality* dan *authenticity* secara total. Selalu biarkan `Cipher.getIV()` dari Keystore yang menentukan random IV.
3. **Mengabaikan Backup Pin pada Certificate Pinning**:
   *Fatal*: Hanya menyematkan satu public key hash pada `network_security_config.xml`. Ketika sertifikat SSL server kadaluarsa atau di-*revoke* darurat, aplikasi yang terpasang di jutaan perangkat pengguna akan terkunci (*bricked*) dan tidak bisa berkomunikasi dengan backend.
4. **Salah Menangani `KeyPermanentlyInvalidatedException`**:
   *Fatal*: Tidak menangani exception saat pengguna mengubah biometrik OS. Aplikasi crash loop tanpa memberikan opsi re-autentikasi atau re-enrollment.

#### Panduan Troubleshooting

| Gejala Error | Akar Masalah | Solusi Penanganan |
| :--- | :--- | :--- |
| `StrongBoxUnavailableException` | Perangkat tidak memiliki chip Secure Element mandiri atau alokasi resource penuh. | Implementasikan blok `try-catch` saat inisialisasi KeyGenParameterSpec, fallback otomatis ke standard TEE (`setIsStrongBoxBacked(false)`). |
| `KeyPermanentlyInvalidatedException` | Pengguna menambahkan atau menghapus sidik jari di pengaturan sistem Android saat flag `setInvalidatedByBiometricEnrollment(true)` aktif. | Tangkap exception ini, hapus alias kunci lama dari `KeyStore.deleteEntry(alias)`, arahkan user ke alur re-login dan re-enrollment kunci baru. |
| `UserNotAuthenticatedException` | Waktu otentikasi biometrik habis (*timeout*) atau `CryptoObject` tidak di-*pass* ke `BiometricPrompt.authenticate()`. | Pastikan operasi kriptografi dieksekusi tepat di dalam callback `onAuthenticationSucceeded` menggunakan objek `result.cryptoObject`. |
| `SSLHandshakeException: Pin verification failed` | Server melakukan rotasi sertifikat tanpa menyertakan root/intermediate yang sesuai dengan pinset aplikasi. | Pastikan implementasi rotasi mencakup dual-pinning: pin sertifikat aktif dan pin sertifikat cadangan (*backup disaster recovery key*). |

---

### 11. Best Practices (Production Checklist)

- [ ] **Hardware-Backed Guarantee**: Gunakan `KeyInfo.isInsideSecureHardware()` untuk memvalidasi bahwa kunci berhasil di-generate di dalam TEE/StrongBox.
- [ ] **Ephemeral Challenge**: Selalu gunakan cryptographically secure random challenge (minimal 32 byte) dari backend saat melakukan *Key Attestation* dan pembuatan payload transaksi.
- [ ] **Enforce Authentication Binding**: Selalu hubungkan private key kritis dengan `setUserAuthenticationRequired(true)` dan passing `BiometricPrompt.CryptoObject`.
- [ ] **Biometric Enrollment Invalidation**: Aktifkan `setInvalidatedByBiometricEnrollment(true)` pada kunci transaksi sensitif.
- [ ] **R8 Obfuscation & Shrinking**: Pastikan `isMinifyEnabled = true` dan `isShrinkResources = true` pada Gradle Release build, serta simpan `mapping.txt` di secure storage server.
- [ ] **Zero Cleartext HTTP**: Konfigurasikan `cleartextTrafficPermitted="false"` pada Network Security Config.
- [ ] **Play Integrity Backend Verification**: Validasi status lisensi, integrity rating (`MEETS_STRONG_INTEGRITY`), dan package name di core service enterprise.
- [ ] **NDK Anti-Debug**: Tanamkan proteksi memory scanning `/proc/self/maps` dan `ptrace(PTRACE_TRACEME)` di layer native C/C++.

---

### 12. Hands-on Practice
Simpan seluruh artefak latihan ini pada struktur direktori: `hands-on/m02/`.

#### Langkah 1: Setup Direktori
Buat struktur folder berikut di dalam project Anda:
```bash
mkdir -p hands-on/m02/app/src/main/cpp
mkdir -p hands-on/m02/app/src/main/java/com/enterprise/security/
mkdir -p hands-on/m02/app/src/main/res/xml
```

#### Langkah 2: Buat File NDK CMakeLists.txt
**File: `hands-on/m02/app/src/main/cpp/CMakeLists.txt`**
```cmake
cmake_minimum_required(VERSION 3.22.1)

project("enterprise-security")

add_library(
        native_security
        SHARED
        anti_tamper.cpp
)

find_library(
        log-lib
        log
)

target_link_libraries(
        native_security
        ${log-lib}
)
```

#### Langkah 3: Buat JNI Wrapper Class
**File: `hands-on/m02/app/src/main/java/com/enterprise/security/NativeSecurityEngine.kt`**
```kotlin
package com.enterprise.security

class NativeSecurityEngine {
    companion object {
        init {
            System.loadLibrary("native_security")
        }
    }

    external fun performIntegrityCheck(): Boolean
}
```

#### Langkah 4: Buat Secure Activity Interactor
**File: `hands-on/m02/app/src/main/java/com/enterprise/security/SecureAuthActivity.kt`**
```kotlin
package com.enterprise.security

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import com.enterprise.security.crypto.SecureCryptoEngine
import java.security.Signature

class SecureAuthActivity : AppCompatActivity() {

    private lateinit var cryptoEngine: SecureCryptoEngine
    private val nativeEngine = NativeSecurityEngine()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cryptoEngine = SecureCryptoEngine(this)

        // 1. Eksekusi Native Tamper Detection
        if (!nativeEngine.performIntegrityCheck()) {
            Toast.makeText(this, "Integritas Perangkat Terkompromi! Menutup aplikasi.", Toast.LENGTH_LONG).show()
            finishAffinity()
            return
        }

        // 2. Generate Key Pair jika belum ada (Biasanya saat registrasi perangkat)
        try {
            val challenge = ByteArray(32).apply { java.security.SecureRandom().nextBytes(this) }
            cryptoEngine.generateHardwareBackedKeyPair(challenge)
        } catch (e: Exception) {
            // Key mungkin sudah ada, lanjutkan
        }

        executeSecureTransaction(byteArrayOf(1, 2, 3, 4, 5))
    }

    private fun executeSecureTransaction(payload: ByteArray) {
        val executor = ContextCompat.getMainExecutor(this)
        val prompt = BiometricPrompt(this, executor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                super.onAuthenticationSucceeded(result)
                val signature = result.cryptoObject?.signature
                if (signature != null) {
                    signature.update(payload)
                    val signedData = signature.sign()
                    Toast.makeText(this@SecureAuthActivity, "Transaksi berhasil ditandatangani hardware!", Toast.LENGTH_SHORT).show()
                    // Kirim payload + signedData ke backend
                }
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                super.onAuthenticationError(errorCode, errString)
                Toast.makeText(this@SecureAuthActivity, "Autentikasi gagal: $errString", Toast.LENGTH_SHORT).show()
            }
        })

        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("Otorisasi Transaksi Finansial")
            .setSubtitle("Pindai sidik jari Anda untuk menandatangani data")
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText("Batal")
            .build()

        val cryptoObject = cryptoEngine.createCryptoObject()
        prompt.authenticate(promptInfo, cryptoObject)
    }
}
```

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi utilitas enkripsi simetris menggunakan `AES-256-GCM` via Android Keystore:
- Kunci disimpan di `AndroidKeyStore`.
- Menggunakan `KeyGenParameterSpec` dengan `PURPOSE_ENCRYPT or PURPOSE_DECRYPT`.
- Simpan IV bersama ciphertext (prepend IV 12-byte ke payload terenkripsi).

#### Level: Medium
Modifikasi `SecureCryptoEngine` untuk mendukung **Key Rotation**:
- Tambahkan kemampuan untuk membuat versi kunci baru (`KEY_ALIAS_V2`) tanpa menghapus kunci lama terlebih dahulu.
- Lakukan proses dekripsi data migrasi dengan kunci lama, lalu re-enkripsi dengan kunci baru.
- Hapus entri kunci lama dari Keystore hanya jika re-enkripsi berhasil secara atomik.

#### Level: Hard
Kembangkan native dynamic check pada file C++:
- Buat thread native terpisah (`pthread_create`) yang melakukan *polling watchdog* setiap 1 detik.
- Thread tersebut harus memeriksa `/proc/self/status` untuk membaca flag `TracerPid`. Jika `TracerPid != 0`, eksekusi terminating signal via `raise(SIGKILL)` secara instan untuk mencegah debugger/Frida membaca memory aplikasi.

---

### 14. Challenge

**Skenario**: Anda memimpin tim arsitektur keamanan untuk sistem otorisasi pembayaran perbankan (*High-Risk Offline Token*). Klien harus membuat dynamic One-Time-Signature (OTS) secara *offline* yang tidak dapat dimanipulasi atau diekstraksi dari perangkat, namun server backend harus dapat memvalidasi bahwa token tersebut dihasilkan dari chip TEE/StrongBox yang sah saat perangkat online kembali.

**Tugas Anda**:
1. Rancang arsitektur protokol registrasi kunci asimetris dan pengiriman signed claims offline.
2. Jelaskan bagaimana Anda menangani sinkronisasi waktu dan perlindungan terhadap *clock tampering* di level OS Android ketika perangkat offline.
3. Desain mekanisme pertahanan jika aplikasi dijalankan pada perangkat dengan OS hasil kompilasi kustom (Custom AOSP ROM) yang memalsukan respons JNI Biometric framework. Tunjukkan bagaimana rantai validasi Anda menolak request tersebut.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Di manakah private key disimpan saat menggunakan Android Keystore dengan implementasi TEE?**
   - A. Di dalam database terenkripsi SQLite aplikasi.
   - B. Di dalam file shared_prefs dalam bentuk base64.
   - C. Di dalam memori terisolasi TrustZone yang tidak dapat diakses langsung oleh OS Android.
   - D. Di dalam direktori `/data/system/users/0/`.
   *Jawaban*: **C**. Hardware-backed keystore mengisolasi private key di dalam TEE (TrustZone) atau StrongBox (SE).

2. **Apa peran dari parameter `setInvalidatedByBiometricEnrollment(true)`?**
   - A. Menghapus data biometrik dari sistem Android.
   - B. Membatalkan (menjadikan invalid secara permanen) kunci Keystore jika ada sidik jari baru yang didaftarkan di OS.
   - C. Mengharuskan aplikasi diinstal ulang saat user berganti password lockscreen.
   - D. Mempercepat proses otentikasi biometrik.
   *Jawaban*: **B**. Flag ini mencegah serangan di mana penyerang yang mengetahui passcode lockscreen menambahkan sidik jarinya sendiri untuk membajak otentikasi aplikasi.

3. **Mengapa algoritma AES-GCM lebih disukai daripada AES-CBC untuk penyimpanan data lokal aplikasi enterprise?**
   - A. Karena AES-GCM tidak membutuhkan Initialization Vector (IV).
   - B. Karena AES-GCM menyediakan Authenticated Encryption with Associated Data (AEAD) yang menjamin kerahasiaan dan integritas data sekaligus.
   - C. Karena AES-GCM berjalan lebih cepat pada CPU 32-bit tanpa hardware acceleration.
   - D. Karena AES-CBC sudah di-deprecate oleh Google Play Store.
   *Jawaban*: **B**. AES-GCM adalah AEAD cipher yang memverifikasi keaslian (autentikasi) ciphertext menggunakan Authentication Tag, mencegah bit-flipping attacks.

4. **Kapan `BiometricPrompt.CryptoObject` harus digunakan dalam flow otentikasi?**
   - A. Hanya jika perangkat tidak memiliki koneksi internet.
   - B. Hanya saat kita ingin menampilkan ikon sidik jari kustom.
   - C. Setiap kali kita ingin mengikat otentikasi biometrik secara langsung ke pembukaan operasional kunci kriptografis di hardware Keystore.
   - D. Ketika kita menggunakan Android versi 8.0 (Oreo) ke bawah.
   *Jawaban*: **C**. `CryptoObject` menjamin hardware-level cryptographic release yang tidak bisa di-bypass sekadar dengan memanipulasi kode UI return callback.

5. **Apa fungsi dari atribut `cleartextTrafficPermitted="false"` pada Network Security Config?**
   - A. Mengompresi seluruh trafik HTTP.
   - B. Memblokir seluruh koneksi HTTP yang tidak terenkripsi (plain text) pada seluruh aplikasi.
   - C. Menghapus log TLS/SSL dari Logcat.
   - D. Mengaktifkan DNS-over-HTTPS.
   *Jawaban*: **B**. Atribut ini memaksa seluruh koneksi jaringan aplikasi menggunakan protokol aman (HTTPS/TLS) dan memblokir traffic cleartext HTTP.

#### Bagian 2: Intermediate (5 Soal)
6. **Apa perbedaan struktural utama antara StrongBox KeyMint dan standar TEE?**
   - A. StrongBox diimplementasikan menggunakan perangkat lunak, sedangkan TEE menggunakan perangkat keras.
   - B. StrongBox menggunakan dedicated secure element chip terpisah dengan CPU & RAM sendiri, sedangkan TEE berbagi silikon prosesor utama melalui pemisahan ARM TrustZone.
   - C. StrongBox memiliki performa kriptografi lebih tinggi dibanding TEE.
   - D. StrongBox tidak memerlukan attestation certificate.
   *Jawaban*: **B**. StrongBox adalah modul hardware mandiri (contoh: chip Titan M2) yang fisik dan jalurnya terpisah dari Application Processor (AP), memberikan proteksi fisik maksimal terhadap side-channel attacks.

7. **Bagaimana implementasi `ptrace(PTRACE_TRACEME, 0, 1, 0)` melindungi aplikasi dari dynamic instrumentation seperti Frida/GDB?**
   - A. Menghapus socket server Frida dari port sistem.
   - B. Mengenkripsi executable ELF di dalam memory.
   - C. Kernel Linux membatasi proses hanya boleh di-attach oleh satu tracer; jika dipanggil lebih dulu oleh aplikasi, tracer eksternal akan gagal meng-attach dirinya.
   - D. Memaksa aplikasi berjalan dalam mode sandbox SELinux enforcing.
   *Jawaban*: **C**. Prinsip dasar tracing kernel Linux melarang lebih dari satu proses meng-attach target via `PTRACE_ATTACH`/`PTRACE_TRACEME`.

8. **Mengapa verifikasi rantai sertifikat Key Attestation HARUS dilakukan di backend server, bukan di aplikasi Android?**
   - A. Sertifikat X.509 terlalu besar untuk diparsing oleh Android OS.
   - B. Jika OS telah di-compromise atau di-hook (misal via Zygisk), logika verifikasi di client dapat dipalsukan untuk selalu mengembalikan nilai true.
   - C. Google API melarang validasi sertifikat lokal.
   - D. Attestation challenge hanya bisa di-generate oleh Google server.
   *Jawaban*: **B**. Sesuai prinsip Zero-Trust: Klien Android berada pada *untrusted environment*. Seluruh bukti kriptografis harus diverifikasi oleh *trusted environment* (Backend).

9. **Apa risiko arsitektur dari menyematkan Certificate Pinning langsung ke Leaf Certificate (Server Cert) dibandingkan Intermediate/Root CA Certificate?**
   - A. Tidak aman terhadap serangan Man-in-the-Middle.
   - B. Memerlukan update aplikasi secara paksa (force-update) setiap kali sertifikat leaf kedaluwarsa (biasanya setiap 90 hari sesuai standar CA modern).
   - C. Menurunkan kecepatan handshake TLS hingga 50%.
   - D. Membuat aplikasi ditolak oleh Google Play Store.
   *Jawaban*: **B**. Leaf certificate memiliki masa berlaku yang sangat pendek. Pinning pada SPKI Public Key dari Intermediate CA atau menyertakan backup disaster pin memberikan fleksibilitas rotasi sertifikat tanpa merusak instalasi aplikasi pengguna.

10. **Apa yang terjadi pada level Android Keystore jika pengguna menghapus screen lock (PIN/Password/Biometrik) di pengaturan sistem?**
    - A. Keystore secara otomatis mengganti password kunci dengan string kosong.
    - B. Seluruh kunci yang diinisialisasi dengan `setUserAuthenticationRequired(true)` akan dihapus atau dimatikan secara permanen oleh OS Keystore daemon demi keamanan.
    - C. Kunci diekspor otomatis ke Google Drive Backup.
    - D. Kunci dialihkan ke Software-backed Keystore.
    *Jawaban*: **B**. OS Keystore daemon secara otomatis menghapus otorisasi hardware-bound cryptographic keys jika cryptographic root auth-nya (PIN/Pattern/Biometric) ditiadakan oleh pengguna.

#### Bagian 3: Kasus Produksi Enterprise (3 Skenario)
11. **Skenario Kasus 1**:
    Sebuah aplikasi fintech mendapati ratusan akun melakukan *transfer spamming* dengan waktu identik hingga satuan milidetik. Tim audit menemukan bahwa attacker menggunakan Frida script untuk meng-hook method `onClick` pada tombol transfer dan memanggil logic REST API secara langsung.
    Bagaimana Anda merancang mitigasi menyeluruh yang tidak dapat ditembus hanya dengan memanipulasi runtime Java/Kotlin?
    *Jawaban Analisis Arsitektur*:
    - Hapus ketergantungan otorisasi pada flag level Java.
    - Terapkan skema *Hardware-Bound Dynamic Signing*: Setiap eksekusi transfer mewajibkan backend mengirimkan *single-use cryptographic nonce*.
    - Nonce + detail payload transfer harus ditandatangani di dalam hardware Keystore via `BiometricPrompt.CryptoObject` menggunakan ECDSA private key.
    - Attacker yang melakukan hooking pada method `onClick` tidak akan dapat menghasilkan signature yang valid tanpa otentikasi biometrik asli yang membuka kunci hardware TEE. Backend akan menolak seluruh request yang tidak memiliki signature valid atas nonce tersebut.

12. **Skenario Kasus 2**:
    Setelah merilis update aplikasi dengan Play Integrity API, Anda mendapati bahwa sekitar 12% pengguna sah di negara berkembang mengalami error integrasi (`MEETS_BASIC_INTEGRITY` lolos, tetapi `MEETS_STRONG_INTEGRITY` gagal).
    Apa akar masalahnya dan bagaimana arsitektur enterprise menangani degradasi ini tanpa mengorbankan keamanan?
    *Jawaban Analisis Arsitektur*:
    - `MEETS_STRONG_INTEGRITY` mewajibkan perangkat memiliki hardware-backed bootloader verification dan TEE/KeyMint tersertifikasi resmi. Banyak perangkat murah (OEM lokal/low-end) menggunakan bootloader software atau tidak tersertifikasi Google penuh, sehingga gagal memenuhi evaluasi level STRONG.
    - Solusi: Terapkan **Tiered Risk-Based Access Control** di backend:
      - Transaksi bernilai tinggi (misal transfer > Rp 50.000.000): Wajib memenuhi `MEETS_STRONG_INTEGRITY`.
      - Transaksi bernilai rendah / operasional standar: Boleh berjalan pada perangkat yang hanya lolos `MEETS_DEVICE_INTEGRITY` / `MEETS_BASIC_INTEGRITY`, namun disertai faktor proteksi tambahan (misal: SMS OTP step-up authentication atau daily limit restriction).

13. **Skenario Kasus 3**:
    Perusahaan Anda mengalami insiden darurat: Sertifikat SSL backend utama terancam bocor karena kerentanan pada penyedia infrastruktur cloud. Tim infrastruktur mengganti sertifikat TLS dalam waktu 2 jam. Namun, 500.000 pengguna aktif aplikasi Anda tiba-tiba tidak dapat membuka aplikasi sama sekali (`SSLHandshakeException`).
    Apa kesalahan desain arsitektur pada Network Security Config aplikasi Anda, dan bagaimana prosedur pemulihannya?
    *Jawaban Analisis Arsitektur*:
    - **Kesalahan Desain**: Tim keamanan menerapkan Certificate Pinning hanya dengan 1 buah pin hash (Leaf Cert pin) tanpa mendefinisikan *Backup Pins* (seperti Root/Intermediate CA backup pin atau Standby Disaster Key pin) sebagaimana diwajibkan dalam standar security engineering.
    - **Prosedur Pemulihan**:
      - Cara cepat: Minta tim infrastruktur mengonfigurasi sertifikat baru di web server/load balancer agar menggunakan Public Key (SPKI) yang persis sama dengan sertifikat lama (membuat CSR menggunakan private key lama jika safe, atau menggunakan keypair dari CA yang cocok dengan hash lama).
      - Rilis darurat aplikasi (Hotfix APK) ke Play Store dengan konfigurasi pinset baru, lalu dorong notifikasi update melalui channel Play In-App Updates atau Play console expedited review.

---

### 16. Summary
- **Android Keystore System** mengisolasi material kunci dari userspace OS ke hardware tersertifikasi (**TEE** dan **StrongBox**). Private key tidak pernah diekspos ke memori aplikasi.
- **Biometric Integration via `CryptoObject`** mengunci operasi kriptografi di hardware KeyMint, mencegah bypass otentikasi oleh dynamic instrumentation framework seperti Frida.
- **Key Attestation & Play Integrity** menyediakan rantai pembuktian hardware dan integritas aplikasi yang dapat diverifikasi oleh backend secara asinkron dan bebas dari tampering client-side.
- **Native Hardening (NDK C++)** memperluas defense-in-depth melalui system-level tracing mitigation (`ptrace`) dan virtual memory maps inspection.
- Keamanan mobile enterprise menolak asumsi *trust-on-client*. Pendekatan yang benar adalah menerapkan **Zero-Trust Client Architecture**, di mana klien bertindak sebagai entitas pembukti kriptografis dan backend memegang kendali penuh otorisasi melalui validasi integritas berlapis.