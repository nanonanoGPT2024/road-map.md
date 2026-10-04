# BAB 08: Quiz, Challenge, & Knowledge Check
**Android Security, Keystore, & App Hardening**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Android Application Sandbox & Linux UID Isolation**
   Jelaskan secara mendalam bagaimana Android mengimplementasikan isolasi proses antar aplikasi memanfaatkan kernel Linux. Mengapa mekanisme standard UNIX User Identifier (UID) dimodifikasi sedemikian rupa oleh Android, dan apa implikasi keamanannya terhadap akses filesystem `/data/data/<package_name>` serta komunikasi antar-komponen via Binder IPC?

2. **Android Keystore Provider vs Private Storage Encryption**
   Apa perbedaan arsitektural mendasar antara mengenkripsi data menggunakan algoritma AES-GCM dengan *key* yang disimpan di dalam internal storage (misal via SharedPreferences terproteksi file permissions) versus mendelegasikan cryptographic lifecycle ke Android Keystore Provider? Analisis dari perspektif *key extraction resistance* pada perangkat yang telah mengalami *rooting*.

3. **Master Key Hierarchy pada Jetpack Security (Tink)**
   Jelaskan arsitektur enkripsi berlapis (*envelope encryption*) yang digunakan oleh pustaka `EncryptedSharedPreferences` dan `EncryptedFile` (Jetpack Security / Google Tink). Bagaimana korelasi antara *Key Encryption Key* (KEK) yang berada di Hardware-backed Keystore dan *Data Encryption Key* (DEK) yang berada di *keyset* lokal?

4. **Network Security Config vs Custom TrustManager**
   Mengapa implementasi manual `X509TrustManager` dan `SSLSocketFactory` untuk Certificate Pinning sangat rentan terhadap kesalahan implementasi (*catastrophic vulnerability*), dan bagaimana deklarasi deklaratif via `res/xml/network_security_config.xml` memitigasi risiko *man-in-the-middle* (MITM) sembari tetap mendukung mekanisme *cleartext traffic elimination* dan *certificate rotation*?

5. **R8/ProGuard: Shrinking, Optimization, & Obfuscation**
   R8 tidak hanya bertindak sebagai *obfuscator*, melainkan juga compiler toolchain. Jelaskan perbedaan mendasar antara *tree shaking (shrinking)*, *bytecode optimization*, dan *identifier renaming*. Mengapa *reflection* dan serialisasi data (seperti Gson/Moshi) sering kali rusak (*crash runtime*) saat R8 aktif jika `-keep` rules tidak dikonfigurasi secara presisi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **BiometricPrompt Cryptographic Binding & Key Invalidation**
   Ketika menginisialisasi `KeyGenParameterSpec` dengan flag `setUserAuthenticationRequired(true)`, jelaskan siklus hidup *crypto-bound auth token* yang diverifikasi oleh `BiometricPrompt`. Mengapa penambahan sidik jari/wajah baru di sistem Android (Enrollment baru) secara default memicu `KeyPermanentlyInvalidatedException`? Mekanisme kernel/TEE apa yang mendeteksi perubahan state biometrik ini?

2. **TEE (Trusted Execution Environment) vs StrongBox Keymaster/KeyMint**
   Bandingkan arsitektur eksekusi kriptografi pada TEE standard (ARM TrustZone) dengan StrongBox Keymaster (Dedicated Hardware Security Module / Secure Element terpisah). Kapan seorang arsitek sistem harus menetapkan `setIsStrongBoxBacked(true)`, dan apa batasan *throughput*, latensi, serta kapasitas penyimpanan yang harus dikorbankan?

3. **Play Integrity API: Cryptographic Verification Flow**
   Jelaskan alur *end-to-end* validasi integritas menggunakan Play Integrity API. Mengapa verifikasi token integritas **wajib** dilakukan di backend server perusahaan dan bukan secara lokal di aplikasi Android? Bagaimana parameter `nonce` dikonstruksi secara kriptografis untuk mencegah serangan *replay attack*?

4. **In-Memory Secret Sanitization & JVM Garbage Collector Leakage**
   Mengapa menyimpan data sensitif (seperti PIN, private key, atau pass-phrase) dalam tipe data `java.lang.String` dianggap sebagai *high-risk security flaw* pada audit perbankan? Bagaimana heap memory dump via runtime debug/root dapat mengekstraksi data tersebut meskipun variabel sudah di-*null*-kan, dan bagaimana penggunaan `CharArray` atau `ByteArray` dengan teknik *explicit zeroing* (`Arrays.fill(0)`) memitigasinya?

5. **Dynamic Instrumentation (Frida) & Detection Vector**
   Bagaimana cara kerja *dynamic binary instrumentation* seperti Frida dalam memanipulasi *return value* fungsi enkripsi atau *bypass* SSL pinning pada level ART (Android Runtime)? Sebutkan minimal tiga vektor inspeksi lingkungan (*environment heuristics*) yang digunakan oleh SDK anti-tampering untuk mendeteksi keberadaan Frida (misal: *named pipes*, port scanning, dan memory-mapped files di `/proc/self/maps`).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Skala Besar — Dynamic Bypass & Mass Credential Extraction
Sebuah aplikasi dompet digital enterprise dengan 5 juta pengguna aktif mengalami serangan terstruktur. Hacker berhasil mempublikasikan skrip Frida di GitHub yang mampu melakukan *hooking* pada kelas validasi SSL bawaan dan mem-bypass *Certificate Pinning*. Dampaknya, trafik transaksi finansial berhasil di-intersep di jaringan publik, dan access token OAuth 2.0 milik ribuan pengguna bocor. 

* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda merancang arsitektur pertahanan berlapis (*Defense-in-Depth*) untuk menanggulangi *dynamic hook* tersebut secara langsung, baik dari sisi Network Layer, Native Layer (C/C++ NDK), hingga App Runtime?
  2. Bagaimana strategi Anda merekayasa *token invalidation* dan migrasi Certificate Pinning secara *zero-downtime* ke seluruh armada perangkat klien tanpa memblokir pengguna sah yang belum memperbarui aplikasi?

---

### Skenario B: Race Condition & Crash Loop — MasterKey Deadlock & State Invalidation
Setelah peluncuran versi baru aplikasi FinTech, tingkat *crash* melonjak hingga 14% khusus pada perangkat Samsung dan Google Pixel berbasis Android 12+. Log produksi menunjukkan `java.security.ProviderException: Failed to generate key` dan `KeyPermanentlyInvalidatedException` yang berulang saat aplikasi mengakses `EncryptedSharedPreferences`. Investigasi awal menunjukkan bahwa aplikasi menginisialisasi enkripsi secara paralel dari `Application.onCreate()` dan beberapa background `Worker` (WorkManager) secara bersamaan, tepat setelah pengguna mengubah kunci layar (*lock screen pattern/PIN*) mereka.

* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi *root cause* dari *deadlock/race condition* pada Android Keystore saat inisialisasi kunci master secara paralel di multi-threading/multi-process.
  2. Rancang pola arsitektur inisialisasi yang *thread-safe*, *idempotent*, dan memiliki *recovery mechanism* otomatis (fall-back/graceful re-authentication) tanpa menghilangkan data lokal pengguna yang telah terenkripsi sebelumnya.

---

### Skenario C: Arsitektur & Trade-off — Low-Latency Signing vs High-Assurance StrongBox
Sebuah bank investasi internasional meminta Anda membangun aplikasi Android untuk otorisasi transaksi bernilai tinggi (*high-frequency approval*). Regulasi mewajibkan setiap request transaksi ditandatangani secara kriptografis (*digital signature*) langsung di perangkat menggunakan private key hardware-backed. Namun, pengujian laboratorium menunjukkan:
* TEE Signature: Latensi ~15-30ms per signature.
* StrongBox KeyMint Signature: Latensi ~450-800ms per signature, dan sering melempar `StrongBoxUnavailableException` pada perangkat vendor tertentu.
* Tim bisnis menolak latensi StrongBox karena merusak UX transaksi *real-time*, tetapi tim *compliance* menuntut level keamanan tertinggi hardware-grade EAL5+.

* **Pertanyaan Diagnostik & Solusi:**
  1. Buat evaluasi matriks trade-off teknis antara penggunaan TEE vs StrongBox untuk kasus ini.
  2. Rancang arsitektur kriptografi hibrida (*hybrid cryptographic scheme*) yang memenuhi standar kepatuhan regulasi finansial tanpa membebani thread antarmuka (UI) dan tetap menjaga responsivitas transaksi pengguna.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Secure Offline Vault with Biometric Attestation & Anti-Tamper Shield

#### Deskripsi Masalah
Anda diminta membangun modul *Secure Local Storage Engine* untuk aplikasi militer/intelijen independen. Modul ini bertanggung jawab menyimpan koordinat dan data intelijen lokal secara terenkripsi di perangkat. Jika perangkat jatuh ke tangan musuh, data tidak boleh dapat diekstraksi meskipun perangkat di-root, dihubungkan ke hardware debugger (JTAG/ADB), atau dianalisis via memory dumping dan dynamic instrumentation.

#### Requirements Teknis
1. **Hardware-Backed Master Key:**
   * Inisialisasi Master Key menggunakan AES-256-GCM melalui Android Keystore.
   * Kunci harus secara tegas meminta otentikasi biometrik pengguna (`BIOMETRIC_STRONG`) untuk setiap operasi read/write dengan batas timeout otentikasi 0 detik (setiap akses crypto wajib menyertakan instance `BiometricPrompt.CryptoObject` yang valid).
   * Kunci harus di-bind ke hardware StrongBox jika tersedia pada perangkat; jika tidak, lakukan graceful fallback ke ARM TEE dengan audit telemetry log.
2. **Envelope Data Encryption Engine:**
   * Gunakan format enkripsi kustom: Master Key (KEK) hanya mengenkripsi Session/Data Key (DEK). 
   * Data payload dienkripsi dengan DEK menggunakan AES-256-GCM beserta *Authenticated Associated Data* (AAD) yang mengikat `package_name` dan tanda tangan SHA-256 sertifikat rilis aplikasi.
3. **In-Memory Sanitization:**
   * Tidak boleh ada `String` yang menampung *plaintext* atau *intermediate decrypted payload*. Seluruh transmisi payload lokal wajib menggunakan `ByteArray` / direct NIO `ByteBuffer` yang di-overwrite dengan nilai nol (`0x00`) via blok `finally`.
4. **Active Tamper Defense Layer (NDK / C++ Layer):**
   * Buat library C++ via JNI yang mengeksekusi pemeriksaan integritas di latar belakang: deteksi status *ptrace* (anti-debugging via `PT_DENY_ATTACH` atau pembacaan status `/proc/self/status` field `TracerPid`), verifikasi integritas checksum binary `.so` di memori, dan pendeteksian direktori/environment Magisk/KernelSU.
   * Jika anomali terdeteksi, modul harus secara otomatis memusnahkan (*zeroize*) KEK di Keystore dan memicu crash aplikasi seketika (*fail-closed*).

#### Constraints & Batasan
* Bahasa: Kotlin 1.9+ & Modern C++ (CMake, Clang toolchain).
* Min SDK: 26 (Android 8.0) | Target SDK: 34 (Android 14).
* Tidak diperbolehkan menggunakan pustaka third-party non-Google/non-Jetpack (Hanya boleh menggunakan standard Java Cryptography Architecture / Android Keystore, Jetpack Security, dan Android NDK Native API).
* Wajib menangani lifecycle `KeyPermanentlyInvalidatedException` (misal: saat pendaftaran biometrik baru terjadi).

#### Expected Output
* File arsitektur modular yang berisi:
  1. `CryptoManager.kt`: Mengelola lifecycle Keystore, fallback StrongBox ke TEE, inisialisasi `Cipher`, dan binding ke `CryptoObject`.
  2. `SecurityEnclaveVault.kt`: Menyediakan API baca/tulis *stream-based* memory-safe menggunakan format envelope encryption + AAD.
  3. `native-defense.cpp`: Implementasi native anti-debugging (`TracerPid`), pemeriksaan memori `/proc/self/maps`, dan verifikasi environment integrity.
* Unit Test & Security Integration Test yang membuktikan bahwa eksekusi dekripsi gagal jika AAD diubah atau bila dieksekusi tanpa otentikasi biometrik yang valid.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Android Keystore, pemisahan proses antara `keystored` daemon, Hardware Abstraction Layer (HAL), TEE, dan StrongBox/SE.
- [ ] Perbedaan kriptografis antara cipher modes (misal: ECB [tidak aman], CBC [membutuhkan padding & rentan oracle attack], dan GCM [AEAD - Authenticated Encryption with Associated Data]).
- [ ] Cara kerja Play Integrity API, termasuk pembuatan payload attestation, enkripsi token, dan alur validasi server-side via Google API.
- [ ] Vektor serangan de-obfuscation bytecode DEX melalui tools seperti Jadx, Ghidra, dan mekanisme proteksi kontrol alur (*control-flow flattening*).
- [ ] Siklus hidup kunci kriptografi yang terikat dengan status layar kunci (L-Lock screen credentials) dan manajemen `KeyPermanentlyInvalidatedException`.
- [ ] Konsep Memory Safety pada Android Runtime (ART) dan bahaya eksfiltrasi data via Core Memory Dumps.

### Saya tidak perlu menghafal:
- [ ] Notasi matematis kurva eliptik tertentu (misal: kurva NIST P-256 vs Curve25519) secara kalkulatif; cukup pahami karakteristik performa dan dukungan platformnya.
- [ ] Kode heksadesimal lengkap dari signature binary Magisk, Frida, atau Xposed framework.
- [ ] Sintaks baris-per-baris dari konfigurasi default ProGuard/R8 untuk ratusan library open-source populer (gunakan panduan resmi vendor/library).
- [ ] Detail implementasi register kernel Linux untuk Binder driver (`/dev/binder`).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `res/xml/network_security_config.xml` untuk Certificate Pinning multi-pin (primary + backup leaf/intermediate/root) beserta bypass debug yang aman.
- [ ] Menulis aturan optimasi dan obfuscasi R8 (`proguard-rules.pro`) tingkat lanjut yang mengaburkan nama kelas bisnis namun mempertahankan serialisasi model tanpa insiden runtime crash.
- [ ] Mengimplementasikan enkripsi data AES-256-GCM menggunakan Android Keystore API modern dengan penanganan otentikasi biometrik interaktif (`BiometricPrompt`).
- [ ] Membangun mekanisme verifikasi integritas aplikasi native via C/C++ (NDK) untuk mendeteksi debugger (`ptrace`), Frida, dan status root secara low-level.
- [ ] Mengaudit heap dump Android menggunakan Eclipse MAT atau Memory Profiler untuk mengidentifikasi kebocoran kredensial plaintext di RAM.