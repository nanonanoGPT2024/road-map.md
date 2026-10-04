# Modul 08.01: Android Security, Keystore, & App Hardening

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Spesialisasi:** Android Engineering
*   **Nomor Bab:** 08
*   **Nomor Modul:** 01
*   **Judul Modul:** Android Security, Keystore, & App Hardening
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat Pengetahuan:** 
    *   Arsitektur OS Android (Linux Kernel, Binder IPC, Zygote, ART runtime)
    *   Kriptografi dasar (Simetris vs Asimetris, Hashing, Message Authentication Code, Digital Certificate X.509)
    *   Kotlin Modern (Coroutines, Flow, High-Order Functions, Memory Management)
    *   Siklus Kompilasi Android (Java Bytecode -> DEX -> R8 Optimization -> APK/AAB Packaging)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda dituntut untuk mampu:

1.  **Menganalisis & Mengisolasi Kunci Kriptografi:** Membangun pipeline manajemen kunci berbasis hardware menggunakan `AndroidKeyStore` provider dengan memanfaatkan isolasi Secure World (TEE dan StrongBox Keymaster/KeyMint).
2.  **Mengimplementasikan Data-at-Rest Encryption Terstandar Industri:** Menerapkan skema enkripsi terotentikasi (Authenticated Encryption with Associated Data / AEAD) menggunakan AES-256-GCM pada level data lokal maupun file storage melalui AndroidX Security Crypto.
3.  **Mencegah Serangan Man-in-the-Middle (MitM) Tingkat Lanjut:** Mengonfigurasi `NetworkSecurityConfig` dan custom TrustManager validation untuk pinning SPKI SHA-256 hash disertai fallback rotasi sertifikat dinamis.
4.  **Mendeteksi Integritas Lingkungan Runtime:** Merancang framework pendeteksian tamper, root access, hook instrumentation (Frida, Xposed), emulator, dan debugging environment secara native (JNI/C++) dan managed code.
5.  **Menerapkan Strategi App Hardening Multilapis:** Mengorkestrasi aturan R8/ProGuard agresif, optimasi DEX name mangling, string encryption, kontrol integritas APK Signature Scheme v2/v3/v4, serta mitigasi memory dumping.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Prinsip Zero Trust pada Client-Side Android
Di dunia arsitektur modern, perangkat klien (ponsel pintar) **selalu dianggap telah terkompromi (untrusted environment)**. Anda tidak memegang kontrol atas modifikasi OS, ketersediaan hook engine (Frida), injeksi dynamic library (`LD_PRELOAD`), hingga dekompilasi APK menjadi Smali. Mental model seorang Staff Mobile Engineer dalam keamanan bukanlah *“membuat aplikasi mustahil diretas”*, melainkan:
1.  **Defense-in-Depth (Pertahanan Berlapis):** Setiap layer (transport, storage, execution, identity) memiliki pertahanan independen. Jebolnya layer transport tidak boleh membuka layer storage.
2.  **Raising the Attack Cost (Menaikkan Biaya Serangan):** Membuat proses eksploitasi begitu mahal secara komputasi, waktu, dan finansial sehingga penyerang meninggalkan sistem Anda.
3.  **Hardware-Rooted Trust:** Memindahkan otoritas material kriptografi paling sensitif dari memori aplikasi (RAM Android yang rawan dump) ke prosesor terisolasi (hardware TEE/StrongBox).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Arsitektur Isolasi Android KeyStore: Rich Execution Environment (REE) vs Trusted Execution Environment (TEE) vs StrongBox

```
+-----------------------------------------------------------------------------+
|                     RICH EXECUTION ENVIRONMENT (REE)                        |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | Application Space (Untrusted / User-space)                            |  |
|  |  [ Your Secure Android App ]                                          |  |
|  |         |                                                             |  |
|  |  [ AndroidX Security Crypto / javax.crypto.Cipher ]                   |  |
|  +---------|-------------------------------------------------------------+  |
|            | Binder IPC (Hardware Abstraction Layer calls)                  |
|  +---------v-------------------------------------------------------------+  |
|  | Android OS Framework Space                                            |  |
|  |  [ keystore2 Daemon ] -> /system/bin/keystore2                        |  |
|  +---------|-------------------------------------------------------------+  |
|            |                                                                |
+------------|----------------------------------------------------------------+
             | Secure Hardware Bus / eSE Interface
+------------v----------------------------------------------------------------+
|                     SECURE WORLD (Hardware Isolation)                       |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | TRUSTED EXECUTION ENVIRONMENT (TEE) - e.g., ARM TrustZone             |  |
|  |  - Keymaster / KeyMint TA (Trusted Application)                       |  |
|  |  - Kunci Privat/Simetris tersimpan di RPMB (Replay Protected Block)   |  |
|  |  - Operasi Kriptografi berjalan di Secure CPU & RAM TEE               |  |
|  |  - RAM OS biasa TIDAK BISA membaca area memori ini                    |  |
|  +-----------------------------------------------------------------------+  |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | STRONGBOX KEYMASTER (Dedicated Hardware - misal: Titan M, NXP eSE)    |  |
|  |  - Terpisah dari CPU Utama (Separate Die & Memory)                    |  |
|  |  - Perlindungan terhadap Physical/Side-Channel Attacks               |  |
|  |  - True Random Number Generator (TRNG) independen                     |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

### 2. Alur Enkripsi / Dekripsi Menggunakan Hardware-Backed Key

```
App Process (REE)                 keystore2 Daemon               TEE/KeyMint (Secure World)
       |                                 |                                   |
       |--- 1. Init Cipher(KeyAlias) --->|                                   |
       |    (Permintaan enkripsi)        |--- 2. Validasi UID & Metadata --->|
       |                                 |    (Akses kontrol hardware)       |
       |                                 |                                   |
       |                                 |<-- 3. Token Operasi Valid --------|
       |<-- 4. CipherEngine Siap --------|                                   |
       |                                 |                                   |
       |--- 5. Cipher.update(Plaintext)->|                                   |
       |                                 |--- 6. Kirim Plaintext Chunk ----->|
       |                                 |    (Kunci TIDAK PERNAH keluar     |
       |                                 |     dari chip hardware)           |
       |                                 |                                   |
       |                                 |    [AES-GCM Engine di TEE]        |
       |                                 |    Encrypt(Data, K) + Calc TAG    |
       |                                 |                                   |
       |                                 |<-- 7. Kembalikan Ciphertext + TAG-|
       |<-- 8. Hasil Ciphertext + TAG ---|                                   |
       |    (Siap disimpan ke DB/Disk)   |                                   |
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Android Keystore Provider & HAL (`KeyMint` / `Keymaster`)
Saat Anda mendeklarasikan pembuatan kunci di dalam Android Keystore, runtime tidak menghasilkan `byte[]` kunci mentah yang bisa diakses oleh kelas JVM Anda. Alih-alih:
*   Framework membuat referensi pointer handle ke objek kunci dalam daemon `keystore2`.
*   Daemon `keystore2` berkomunikasi melalui HAL (Hardware Abstraction Layer) ke modul `Keymaster` (Android 11 kebawah) atau `KeyMint` (Android 12 ke atas).
*   Material kunci dienkripsi menggunakan Root Key milik hardware dan disimpan di persistent storage perangkat (RPMB - Replay Protected Memory Block) atau langsung dienkapsulasi di dalam Secure Element.
*   Bahkan jika hacker memiliki akses root (UID 0), mereka tidak bisa membaca plaintext dari master key, karena operasi kriptografi didelegasikan ke coprocessor terisolasi. Hacker hanya bisa meminta TEE melakukan komputasi enkripsi/dekripsi selama session IPC diizinkan oleh SELinux policy.

### 2. AEAD: Mengapa AES-GCM, Bukan AES-CBC?
Modus operandi konvensional seperti AES-CBC (Cipher Block Chaining) rentan terhadap serangan manipulasi integritas dan padding-oracle attacks:
*   **AES-CBC:** Hanya menyediakan *Kerahasiaan* (Confidentiality). Jika Anda membutuhkan Integritas, Anda wajib mengombinasikannya secara manual dengan HMAC (skema Encrypt-then-MAC). Kesalahan implementasi (misalnya MAC-then-Encrypt) membawa celah fatal.
*   **AES-GCM (Galois/Counter Mode):** Merupakan skema AEAD. Menggabungkan mode Counter (CTR) untuk kerahasiaan dan perkalian Galois field untuk autentikasi integritas. Menghasilkan *Ciphertext* dan *Authentication Tag* (umumnya 128 bit). Jika ciphertext atau Initialization Vector (IV) diubah 1 bit saja di media disk, tahap dekripsi akan gagal seketika (`AEADBadTagException`).

### 3. R8 Compiler & ProGuard Architecture
R8 adalah optimator dan desugaring engine yang berjalan saat proses build APK:
*   **Shrinking:** Menganalisis grafik dependensi via Static Reachability Analysis. Kelas dan fungsi yang tidak terpanggil akan dihapus dari DEX.
*   **Optimization:** Inlining method, unboxing class wrapper, devirtualization panggilan fungsi.
*   **Obfuscation (Name Mangling):** Mengubah identifier kelas, variabel, dan signature (`com.enterprise.PaymentRepositoryImpl` -> `a.b.a`) untuk merusak pemahaman semantik penyerang saat membaca hasil dekompilasi CFR, Jadx, atau Baksmali.
*   **Metadata Stripping:** Menghapus debug line numbers, source file attributes, dan parameter annotations.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Parameter Otentikasi User pada Keystore
Keystore memungkinkan kunci diikat secara kriptografis dengan status biometrik pengguna menggunakan flag:
*   `setUserAuthenticationRequired(true)`: Kunci terkunci hingga user memvalidasi identitas via Biometrik (Fingerprint/Face) atau Lock Screen (PIN/Pattern/Password).
*   `setUserAuthenticationParameters(timeoutSeconds, KeyProperties.AUTH_BIOMETRIC_STRONG)`: Menetapkan validitas kunci. Jika `timeoutSeconds = 0` (atau `AUTH_PER_OPERATION`), sistem memerlukan objek `BiometricPrompt.CryptoObject` yang terikat pada instance `Cipher` aktif. Keystore memanfaatkan *Auth Token* bertanda tangan HMAC yang diterbitkan oleh `Gatekeeper` atau `Fingerprint HAL` di TEE untuk membuka kunci hanya untuk 1 sesi operasi kriptografi tersebut.
*   `setInvalidatedByBiometricEnrollment(true)`: Jika penyerang berhasil membobol PIN perangkat dan mendaftarkan sidik jari mereka sendiri di OS Settings, kunci kriptografi otomatis dimusnahkan secara permanen di level TEE.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi modul kriptografi modern berbasis `AES-256-GCM` yang aman dengan fallback isolasi StrongBox jika perangkat mendukungnya.

```kotlin
package com.enterprise.security.crypto

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.nio.ByteBuffer
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class HardwareCryptoEngine(private val context: Context) {

    companion object {
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val MASTER_KEY_ALIAS = "EnterpriseSecMasterKey"
        private const val AES_GCM_NO_PADDING = "AES/GCM/NoPadding"
        private const val GCM_IV_LENGTH_BYTES = 12
        private const val GCM_TAG_LENGTH_BITS = 128
    }

    private val keyStore: KeyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply {
        load(null)
    }

    init {
        ensureMasterKeyExists()
    }

    private fun ensureMasterKeyExists() {
        if (!keyStore.containsAlias(MASTER_KEY_ALIAS)) {
            generateMasterKey()
        }
    }

    private fun generateMasterKey() {
        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            ANDROID_KEYSTORE
        )

        val purposes = KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        val builder = KeyGenParameterSpec.Builder(MASTER_KEY_ALIAS, purposes)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setRandomizedEncryptionRequired(true)

        // Cek dukungan StrongBox Keymaster (Dedicated Hardware Chip terpisah)
        val hasStrongBox = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            context.packageManager.hasSystemFeature(PackageManager.FEATURE_STRONGBOX_KEYSTORE)
        } else {
            false
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && hasStrongBox) {
            try {
                builder.setIsStrongBoxBacked(true)
                keyGenerator.init(builder.build())
                keyGenerator.generateKey()
                return
            } catch (e: Exception) {
                // Fallback ke TEE standar jika StrongBox alokasinya gagal
            }
        }

        keyGenerator.init(builder.build())
        keyGenerator.generateKey()
    }

    private fun getSecretKey(): SecretKey {
        val entry = keyStore.getEntry(MASTER_KEY_ALIAS, null) as? KeyStore.SecretKeyEntry
            ?: throw IllegalStateException("Key alias not found in Keystore")
        return entry.secretKey
    }

    fun encrypt(plainText: ByteArray, associatedData: ByteArray? = null): ByteArray {
        val cipher = Cipher.getInstance(AES_GCM_NO_PADDING)
        cipher.init(Cipher.ENCRYPT_MODE, getSecretKey())

        // Mengambil IV yang di-generate secara kriptografis aman oleh Keystore
        val iv = cipher.iv
        require(iv.size == GCM_IV_LENGTH_BYTES) { "Invalid IV length generated by Keystore" }

        associatedData?.let {
            cipher.updateAAD(it)
        }

        val cipherText = cipher.doFinal(plainText)

        // Serialisasi: [Panjang IV (4 byte)] + [IV bytes] + [Ciphertext + Auth Tag]
        return ByteBuffer.allocate(4 + iv.size + cipherText.size)
            .putInt(iv.size)
            .put(iv)
            .put(cipherText)
            .array()
    }

    fun decrypt(encryptedPayload: ByteArray, associatedData: ByteArray? = null): ByteArray {
        val buffer = ByteBuffer.wrap(encryptedPayload)
        val ivLength = buffer.int
        require(ivLength == GCM_IV_LENGTH_BYTES) { "Payload corrupted: Invalid IV length" }

        val iv = ByteArray(ivLength)
        buffer.get(iv)

        val cipherText = ByteArray(buffer.remaining())
        buffer.get(cipherText)

        val cipher = Cipher.getInstance(AES_GCM_NO_PADDING)
        val spec = GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)
        cipher.init(Cipher.DECRYPT_MODE, getSecretKey(), spec)

        associatedData?.let {
            cipher.updateAAD(it)
        }

        return cipher.doFinal(cipherText)
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 24:** `KeyStore.getInstance("AndroidKeyStore").apply { load(null) }` — Mengakses SPI (Security Provider Interface) resmi Android Keystore. Argument `null` pada `load()` memberi tahu provider untuk mengakses storage internal OS Keystore yang terisolasi per UID aplikasi.
*   **Baris 40:** `KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT` — Menerapkan *Principle of Least Privilege*. Kunci hanya diizinkan untuk enkripsi dan dekripsi. Kunci ini tidak dapat dieksploitasi untuk `PURPOSE_SIGN` atau `PURPOSE_VERIFY`.
*   **Baris 44:** `.setRandomizedEncryptionRequired(true)` — Memaksa runtime agar penyerang atau developer ceroboh tidak bisa menyediakan Custom IV secara manual. OS mewajibkan entropy hardware yang aman untuk setiap operasi enkripsi.
*   **Baris 48:** `context.packageManager.hasSystemFeature(PackageManager.FEATURE_STRONGBOX_KEYSTORE)` — Menanyakan ServiceManager apakah perangkat memiliki chip tamper-resistant fisik terpisah (contoh: Google Titan M2 pada seri Pixel).
*   **Baris 54:** `builder.setIsStrongBoxBacked(true)` — Mengalokasikan master key langsung ke Secure Element eksternal, bukan sekadar TEE inti prosesor utama.
*   **Baris 78:** `val iv = cipher.iv` — Mengekstrak Initialization Vector acak yang diproduksi oleh secure hardware TRNG.
*   **Baris 81:** `cipher.updateAAD(it)` — Menyuntikkan Associated Authenticated Data (AAD). Metadata ini tidak terenkripsi, tetapi masuk ke perhitungan hash Galois authentication tag. Jika AAD diubah saat pengiriman/penyimpanan, dekripsi akan dibatalkan otomatis.
*   **Baris 87-91:** Mengemas payload menggunakan `ByteBuffer` berformat deterministik agar meminimalisir overhead parsing string (menghindari Base64 yang memakan 33% extra memory jika disimpan mentah dalam binary storage).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Keamanan Aplikasi Mobile Banking Core
Sebuah bank digital multinasional menghadapi ancaman finansial masif:
1.  **Vektor Serangan 1 (Memory Dumping & Frida):** Penyerang menggunakan Magisk-rooted device, me-hook framework `javax.crypto.Cipher` menggunakan Frida script untuk mencuri symmetric token saat disimpan di memory runtime.
2.  **Vektor Serangan 2 (MitM via Custom CA):** User dipaksa menginstal Custom Root CA di setting Android via serangan Social Engineering, lalu proxy Burp Suite digunakan untuk memodifikasi request pemindahan dana (Balance Manipulation).
3.  **Vektor Serangan 3 (Repackaging):** APK di-unpack menggunakan Apktool, kode validasi balance di-bypass pada Smali byte code, dan di-sign ulang menggunakan debugging key.

### Strategi Pertahanan Berlapis (Defense Architecture)
1.  **Transport Security:** Menerapkan Public Key Pinning (SPKI Sha256 Pinning) dengan declarative XML dan dynamic OkHttp Network Interceptor yang memvalidasi Certificate Chain hingga ke SAN (Subject Alternative Name).
2.  **Storage Security:** Menggunakan hybrid encryption di mana payload JSON dienkripsi via hardware AES-256-GCM.
3.  **Runtime Protection (Anti-Tamper Layer):** Validasi integritas APK Signature menggunakan hash certificate resmi secara programatis dan mendeteksi Frida ptrace memory hooking via C++/JNI native inspect file descriptor.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi kelas production-grade untuk menangani Network Pinning, Integrity Checking, dan Anti-Tamper Native Detection.

### 1. Network Pinning & OkHttp Hardening Engine

```kotlin
package com.enterprise.security.network

import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import java.security.KeyStore
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509TrustManager

class SecureNetworkFactory {

    companion object {
        private const val API_DOMAIN = "api.enterprise-bank.com"
        // Backup PIN wajib disertakan untuk rotasi sertifikat agar app tidak bricking
        private const val PRIMARY_PIN = "sha256/k2oTX1jwn0io0gHYq7iizgtTIoV2lM9hoZw4n3B2A+8="
        private const val BACKUP_PIN = "sha256/WoiWRyIOV2lM9hoZw4n3B2A+k2oTX1jwn0io0gHYq7i="
    }

    fun createSecureHttpClient(): OkHttpClient {
        val certificatePinner = CertificatePinner.Builder()
            .add(API_DOMAIN, PRIMARY_PIN)
            .add(API_DOMAIN, BACKUP_PIN)
            .build()

        val systemTrustManager = getSystemTrustManager()

        return OkHttpClient.Builder()
            .certificatePinner(certificatePinner)
            .sslSocketFactory(
                TLSSocketFactoryCompat(), 
                HardenedTrustManager(systemTrustManager)
            )
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .followRedirects(false) // Cegah Open Redirect Attacking
            .followSslRedirects(false)
            .build()
    }

    private fun getSystemTrustManager(): X509TrustManager {
        val factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
        factory.init(null as KeyStore?)
        return factory.trustManagers.first { it is X509TrustManager } as X509TrustManager
    }

    private class HardenedTrustManager(
        private val defaultTrustManager: X509TrustManager
    ) : X509TrustManager {

        @Throws(CertificateException::class)
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
            if (chain.isNullOrEmpty()) {
                throw CertificateException("Empty certificate chain received from host.")
            }

            // 1. Eksekusi standard X509 PKIX path validation
            defaultTrustManager.checkServerTrusted(chain, authType)

            // 2. Custom validation: Tolak sertifikat kadaluarsa atau self-signed
            val leafCert = chain[0]
            leafCert.checkValidity()

            // 3. Verifikasi Extended Key Usage (Server Authentication)
            val extendedKeyUsage = leafCert.extendedKeyUsage
            if (extendedKeyUsage == null || !extendedKeyUsage.contains("1.3.6.1.5.5.7.3.1")) {
                throw CertificateException("Certificate is not explicitly authorized for Server Authentication")
            }
        }

        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {
            defaultTrustManager.checkClientTrusted(chain, authType)
        }

        override fun getAcceptedIssuers(): Array<X509Certificate> = defaultTrustManager.acceptedIssuers
    }
}
```

### 2. Runtime Integrity, Anti-Frida & Root Detection Suite

```kotlin
package com.enterprise.security.tamper

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Process
import java.io.BufferedReader
import java.io.File
import java.io.FileReader
import java.security.MessageDigest

class EnvironmentIntegrityEngine(private val context: Context) {

    companion object {
        // Hash SHA-256 Release Signing Certificate tim internal
        private const val EXPECTED_SIGNATURE_SHA256 = 
            "E3:B0:C4:42:98:FC:1C:14:9A:FB:F4:C8:99:6F:B9:24:27:AE:41:E4:64:9B:93:4C:A4:95:99:1B:78:52:B8:55"
        
        private val KNOWN_ROOT_PATHS = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su"
        )
    }

    fun verifyCompleteSystemIntegrity(): Boolean {
        if (isRootedDevice()) return false
        if (isFridaHookingDetected()) return false
        if (!validateAppSignature()) return false
        return true
    }

    private fun isRootedDevice(): Boolean {
        val buildTags = Build.TAGS
        if (buildTags != null && buildTags.contains("test-keys")) {
            return true
        }

        for (path in KNOWN_ROOT_PATHS) {
            if (File(path).exists()) return true
        }

        // Cek command execution probe
        var process: java.lang.Process? = null
        return try {
            process = Runtime.getRuntime().exec(arrayOf("/system/xbin/which", "su"))
            val reader = BufferedReader(java.io.InputStreamReader(process.inputStream))
            reader.readLine() != null
        } catch (t: Throwable) {
            false
        } finally {
            process?.destroy()
        }
    }

    /**
     * Membaca memory mapping dari Linux `/proc/self/maps`
     * Jika Frida diinjeksi via frida-server atau gadget, modul libc frida atau ptrace port akan tertera di mapping.
     */
    private fun isFridaHookingDetected(): Boolean {
        return try {
            val pid = Process.myPid()
            val mapsFile = File("/proc/$pid/maps")
            if (!mapsFile.exists()) return false

            BufferedReader(FileReader(mapsFile)).use { reader ->
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    val currentLine = line?.lowercase() ?: continue
                    if (currentLine.contains("frida") || 
                        currentLine.contains("gadget") || 
                        currentLine.contains("gum-js-loop")) {
                        return true
                    }
                }
            }
            false
        } catch (e: Exception) {
            // Jika access /proc di-block oleh kernel sandbox yang sangat ketat, anggap aman atau log
            false
        }
    }

    @Suppress("DEPRECATION")
    private fun validateAppSignature(): Boolean {
        return try {
            val packageManager = context.packageManager
            val packageName = context.packageName

            val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val packageInfo = packageManager.getPackageInfo(
                    packageName, 
                    PackageManager.GET_SIGNING_CERTIFICATES
                )
                packageInfo.signingInfo?.apkContentsSigners
            } else {
                val packageInfo = packageManager.getPackageInfo(
                    packageName, 
                    PackageManager.GET_SIGNATURES
                )
                packageInfo.signatures
            }

            if (signatures.isNullOrEmpty()) return false

            val currentCertBytes = signatures[0].toByteArray()
            val md = MessageDigest.getInstance("SHA-256")
            val digest = md.digest(currentCertBytes)
            val currentSignatureHash = bytesToHex(digest)

            currentSignatureHash.equals(EXPECTED_SIGNATURE_SHA256, ignoreCase = true)
        } catch (e: Exception) {
            false
        }
    }

    private fun bytesToHex(bytes: ByteArray): String {
        return bytes.joinToString(":") { String.format("%02X", it) }
    }
}
```

### 3. Konfigurasi Aggressive R8 Rule (`proguard-rules.pro`)

```proguard
# Matikan output debug log mapping
-renamesourcefileattribute SourceFile
-keepattributes SourceFile,LineNumberTable

# Obfuscation dictionary aggression
-repackageclasses 'com.enterprise.sec.internal'
-allowaccessmodification

# Proteksi kelas kriptografi dan tamper detector dari dekompilasi langsung
-keep,allowobfuscation class com.enterprise.security.** {
    public *;
}

# Hapus Log calls level Verbose, Debug, Info dari release DEX
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
    public static int i(...);
}

# Proteksi model serialized dari serialisation stripping bug
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Dimensi | Software Encryption (Conceal/BouncyCastle) | Hardware Keystore (TEE) | StrongBox Keymaster (Dedicated SE) |
| :--- | :--- | :--- | :--- |
| **Lokasi Master Key** | User-Space Process RAM (DEX/Native) | Secure SoC Partition (ARM TrustZone) | Dedicated Isolated Secure Element Chip |
| **Ketahanan Memori Dump** | **Rendah** (Bisa diekstrak via `/proc/pid/mem`) | **Tinggi** (Terisolasi dari OS RAM) | **Maksimum** (Immune to main CPU dumping) |
| **Performa Enkripsi (Throughput)** | Sangat Cepat (Zero IPC latency) | Sedang (Membutuhkan Binder Context Switching) | Paling Lambat (Hardware Bus SPI/I2C Bound) |
| **Dukungan Perangkat** | 100% (Semua OS Android) | ~98% (Android 6.0+) | ~20-30% (Perangkat Flagship Android 9.0+) |
| **Ketahanan Physical Attack** | Nol | Menengah (Rentan cold-boot / fault attack) | Sangat Kuat (Anti-glitch, laser/side-channel) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The IV Re-use Vulnerability in AES-GCM
*   **Kasus Gagal:** Menggunakan Initialisation Vector (IV) yang sama dua kali dengan Master Key yang sama pada AES-GCM.
*   **Dampak:** Hancurnya jaminan integritas kriptografi total (*catastrophic authentication failure*). Penyerang dapat merekonstruksi hash subkey (GHASH Key) dan memalsukan seluruh payload berikutnya tanpa mengetahui kunci AES.
*   **Mitigasi:** Jangan pernah membangkitkan IV sendiri menggunakan generator acak pseudorandom kelas bawah (`java.util.Random`). Selalu gunakan IV otomatis bawaan Keystore (`cipher.iv`) yang disuplai oleh `/dev/urandom` atau hardware TRNG.

### 2. Rotasi Kunci & Penyetelan Network Security Pinning Brick
*   **Kasus Gagal:** Menulis Certificate Pin hardcoded hanya dengan 1 PIN utama. Saat sertifikat backend kadaluarsa atau di-revoke mendadak karena insiden breach, seluruh rilis aplikasi mobile yang beredar tidak dapat lagi menghubungi server (*Permanent Network Outage/Brick*).
*   **Mitigasi:** Wajib sertakan sedikitnya dua nilai PIN hash: Hash dari Leaf Certificate aktif dan Hash dari Intermediate CA/Root CA cadangan atau CSR standby.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menyimpan Kunci Kriptografi di Native Library (`.so` file via NDK)
*   *Pola Pikir Salah:* “Jika saya menulis string kunci di kode C++ (NDK), reverse engineer tidak akan bisa melihatnya melalui dekompilasi Java (Jadx).”
*   *Realita:* String literal di dalam file native C++ dapat diekstrak dalam hitungan detik menggunakan perintah sederhana `strings libnative-lib.so | grep -i key` atau membuka binary di Ghidra/IDA Pro.
*   *Solusi Benar:* Kunci tidak boleh di-*hardcode* di mana pun. Material kunci wajib diproduksi secara dinamis di dalam `AndroidKeyStore` hardware runtime.

### 2. Root Detection Terlalu Rapuh (Naive Execution)
*   *Pola Pikir Salah:* Hanya memeriksa `File("/system/bin/su").exists()`.
*   *Realita:* Framework Magisk modern menggunakan modul *Zygisk* dan mount namespace virtualization yang menyembunyikan file biner `su` dari package list target aplikasi secara sempurna.
*   *Solusi Benar:* Gunakan kombinasi Play Integrity API (Google hardware remote attestation) dipadu dengan native ptrace runtime check dan dynamic canary integrity checking.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan AndroidX EncryptedSharedPreferences dengan Benar:** Selalu inisialisasi menggunakan `MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)` atau `MasterKey.Builder` modern.
2.  **Bersihkan Sensitive Variables dari RAM:** Jangan representasikan password, PIN, atau token sebagai `java.lang.String` (karena String bersifat immutable dan bertahan di Java String Pool hingga garbage collection). Representasikan selalu sebagai `CharArray` atau `ByteArray`, dan timpa nilainya menggunakan `Arrays.fill(sensitiveArray, 0.toByte())` sesegera mungkin setelah pemakaian selesai.
3.  **Tutup Output Debug Logging Secara Total:** Manfaatkan ProGuard/R8 `-assumenosideeffects` untuk menghapus byte code invocation dari `Log.d`, `Log.v`, `Log.i`.
4.  **Terapkan FLAG_SECURE:** Tambahkan `window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)` pada Activity sensitif untuk mencegah sistem OS merekam screenshot di app switcher dan memblokir screen recorder pihak ketiga.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

Operasi IPC dari App (JVM) menuju Hardware Keystore (`keystore2` daemon -> TEE) membutuhkan waktu transisi context switching antar proses Linux yang relatif mahal:
*   **Enkripsi Data Skala Besar:** Jangan mengenkripsi file