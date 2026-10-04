# BAB 09: Quiz, Challenge, & Knowledge Check
**Keamanan Aplikasi iOS & Enkripsi Tingkat Enterprise**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Hierarki Kelas Data Protection API & Rekayasa Siklus Kunci iOS**
   Jelaskan perbedaan mendasar mekanisme kriptografi antara `NSFileProtectionComplete`, `NSFileProtectionCompleteUnlessOpen`, dan `NSFileProtectionCompleteUntilFirstUserAuthentication`. Bagaimana Secure Enclave Processor (SEP) mengabstraksi *Class Key* dari *Hardware UID* perangkat, dan apa implikasi matematisnya terhadap aksesibilitas file ketika perangkat berpindah status dari *locked* ke *unlocked*?

2. **Atribut Aksesibilitas Keychain & Batasan Provisioning Profile**
   Analisis perbedaan keamanan antara `kSecAttrAccessibleAfterFirstUnlock` dan `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`. Mengapa penambahan flag `ThisDeviceOnly` memblokir migrasi *keychain item* ke cadangan iCloud Terenkripsi (iCloud Keychain) atau iTunes Backup, dan bagaimana Keychain Services memanfaatkan *Access Groups* (`kSecAttrAccessGroup`) dalam integrasi App Extensions dengan parent container?

3. **Secure Enclave vs. Application Processor (AP) Memory Isolation**
   Bagaimana alur kerja pembuatan pasangan kunci asimetris (ECC NIST P-256) menggunakan atribut `kSecAttrTokenIDSecureEnclave`? Mengapa *private key* yang digenerate di dalam SEP tidak akan pernah dapat diekstraksi ke dalam heap memory Application Processor (AP), dan bagaimana instruksi verifikasi tanda tangan digital dieksekusi secara terisolasi tanpa membocorkan materi kunci ke ruang alamat aplikasi?

4. **Biometric Authentication: LocalAuthentication (LAContext) vs. Keychain Access Control List (ACL)**
   Bandingkan arsitektur keamanan autentikasi biometrik via `LAContext.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, ...)` murni berbasis software boolean dengan autentikasi yang diikat ke Keychain menggunakan `SecAccessControlCreateWithFlags` (`.biometryCurrentSet` atau `.biometryAny`). Mengapa pendekatan software boolean rentan terhadap manipulasi *dynamic runtime instrumentation* (misal: Frida hook), sedangkan Keychain ACL memberikan jaminan kriptografis *zero-trust*?

5. **CryptoKit Modern vs. Legacy CommonCrypto: AEAD Ciphers & Nonce Lifecycle**
   Jelaskan mengapa algoritma *Authenticated Encryption with Associated Data* (AEAD) seperti AES-GCM dan ChaCha20-Poly1305 pada `CryptoKit` menggantikan mode cipher CBC (Cipher Block Chaining) dengan HMAC terpisah. Mengapa kegagalan mengelola keunikan *Nonce* (Number Used Once) atau *Initialization Vector* (IV) pada AES-GCM berakibat fatal pada integritas *stream key* dan memungkinkan serangan *catastrophic plain-text recovery*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **SSL/TLS Pinning Bypass Mitigation via Defense-in-Depth**
   Implementasi `URLSessionDelegate` konvensional yang meng-override `urlSession(_:didReceive:completionHandler:)` untuk memverifikasi SHA-256 dari *Subject Public Key Info* (SPKI) dapat di-bypass dengan mudah menggunakan skrip Frida yang mem-patch `SecTrustEvaluateWithError`. Rancang strategi mitigasi multi-layer (defense-in-depth) di tingkat native runtime—misalnya memanfaatkan C-level APIs, integrasi Network.framework modern, dan deteksi hook memory—untuk mempertahankan integritas verifikasi sertifikat.

2. **Mitigasi Eksfiltrasi Memory: ARC Heap Retention & String Sanitization**
   Dalam Swift, tipe data primitif seperti `String` dan `Data` dikelola oleh *Automatic Reference Counting* (ARC) dan dapat diduplikasi secara implisit ke dalam heap/buffer memory tanpa deterministik *zeroization*. Bagaimana cara merancang struktur data wrapper (misal: `SecureBuffer` / `SecureBytes`) berbasis unmanaged memory allocation (`posix_memalign`, `mlock`, `memset_s`) untuk mencegah materi rahasia (seperti PIN atau token otentikasi) terbaca melalui memory dump, crash analytics, atau paging swap file iOS?

3. **Arsitektur Jailbreak & Runtime Tampering Detection Tingkat Rendah**
   Pemeriksaan file statis seperti keberadaan `/Applications/Cydia.app` atau penulisan ke `/private` mudah dimanipulasi oleh *jailbreak bypass hooks* (Shadow, Liberty Lite, dsb.). Bagaimana Anda mengimplementasikan deteksi manipulasi lingkungan runtime berbasis C/Assembly tingkat rendah, mencakup:
   - Direct syscalls untuk I/O checks (melewati libc wrapper).
   - Validasi integritas dynamic linker (`_dyld_get_image_name`, `_dyld_get_image_header`) untuk mendeteksi *injected dylibs*.
   - Deteksi debugging via `ptrace` (`PT_DENY_ATTACH`) dan `sysctl` (`KEXEC_FLAG`).

4. **Konfigurasi App Transport Security (ATS) & Custom Certificate Trust Stores**
   Pada infrastruktur enterprise dengan *private Public Key Infrastructure* (PKI) dan inspeksi lalu lintas SSL via Enterprise Proxy, aplikasi sering mengalami kegagalan handshake TLS dengan error `-9807` (`errSSLXCertChainInvalid`) atau `-9802` (`errSSLFatalAlert`). Jelaskan bagaimana mengonfigurasi evaluasi `SecTrust` kustom agar memercayai intermediate/root CA internal perusahaan secara programatis tanpa melonggarkan batasan keamanan global pada `Info.plist` (`NSAppTransportSecurity`).

5. **Sanitasi Background Snapshot & Pencegahan Kebocoran UI/Clipboard**
   Ketika aplikasi beralih ke background, iOS memotret UI aplikasi (`view hierarchy snapshot`) untuk keperluan visual multitask switcher, yang berpotensi membocorkan data PII/Finansial ke disk cache OS tanpa enkripsi. Bagaimana pola desain arsitektural yang tepat untuk menyamarkan UI sebelum rendering snapshot berjalan (`sceneWillResignActive`), dan bagaimana memanfaatkan `UIPasteboard` expiration policy atau `UIPasteboard.general.detectPatterns` untuk memitigasi *cross-app clipboard sniffing*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Pembekuan Massal Jaringan Akibat Rotasi Intermediate CA
Sebuah aplikasi mobile banking enterprise dengan 2 juta pengguna aktif menerapkan *hardcoded leaf certificate pinning* untuk mematuhi regulasi perbankan. Tim Network Ops gateway API pusat secara darurat melakukan *out-of-band certificate rotation* akibat kerentanan zero-day pada private key server.
*Dampaknya:* Semua permintaan API dari aplikasi iOS langsung gagal total dengan error TLS verification failure, mengakibatkan kelumpuhan transaksi nasional. Aplikasi tidak dapat memuat konfigurasi baru karena jalur komunikasi remote-config juga terkena dampak certificate pinning yang sama.

**Pertanyaan Diagnostik & Solusi:**
1. Apa kegagalan fundamental dalam desain pinning arsitektural ini (Leaf Pinning vs. SPKI Pinning / Intermediate CA Pinning)?
2. Bagaimana Anda merancang fallback recovery mechanism yang aman (tanpa membuka celah Man-In-The-Middle) untuk memperbarui trust anchors tanpa harus menunggu rilis darurat App Store yang memakan waktu review 24–48 jam?
3. Formulasikan konfigurasi pinning ideal yang menggabungkan *current key pin*, *backup key pin*, dan validasi *Certificate Transparency (CT) logs*.

---

### Skenario B: Race Condition & Data Corruption pada Background Sync Terenkripsi
Aplikasi rekam medis darurat (EMR) menyimpan riwayat pasien dalam database SQLite terenkripsi (SQLCipher) dengan kunci dekripsi database disimpan di dalam iOS Keychain dengan flag `kSecAttrAccessibleAfterFirstUnlock`.
Aplikasi dikonfigurasi untuk menerima *Silent Push Notifications* (`content-available: 1`) dan menjalankan *Background Tasks* (`BGAppRefreshTask`) untuk mengunduh rekam medis pasien di background secara berkala.
*Masalah:* Di lapangan, ratusan pengguna melaporkan crash fatal bertubi-tubi dengan error `errSecInteractionNotAllowed` (-25308) atau kegagalan pembukaan database (`SQLITE_NOTADB: file is not a database`) saat sinkronisasi background berlangsung sesaat setelah perangkat di-restart namun belum dibuka kuncinya oleh pengguna (*first unlock* belum terjadi).

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa transisi siklus hidup perangkat antara state *Booted -> Locked (Pre-first unlock)* memicu kegagalan pembacaan Keychain dan kegagalan operasi file database SQLCipher?
2. Bagaimana mekanisme koordinasi thread/task (`actor` concurrency atau dispatch barrier) yang harus dibangun untuk menangani kesiapan hardware cryptographic engine sebelum mengakses resource yang dilindungi oleh Data Protection API?
3. Rancang strategi pembagian layer data: data mana yang boleh diakses sebelum *first-unlock*, dan bagaimana menangani sinkronisasi data sensitif secara aman jika push notification tiba sebelum autentikasi awal pengguna?

---

### Skenario C: Zero-Trust Local Storage & Trade-Off Performa pada Enterprise iPad (Multi-Gigabyte)
Sebuah armada enterprise iPad digunakan di fasilitas pertambangan terpencil tanpa koneksi internet selama berminggu-minggu. Aplikasi menyimpan file peta geospasial dan data telemetri berukuran 50 GB. Tim audit keamanan mewajibkan:
1. Seluruh data 50 GB harus dienkripsi dengan standar AES-256.
2. Jika perangkat hilang atau jatuh ke tangan ilegal, data harus dapat dihapus secara instan (*cryptographic erasure*) dalam waktu kurang dari 1 detik ketika mendeteksi tampering atau brute-force PIN.
3. Waktu *read/write latency* untuk streaming peta tidak boleh menyebabkan frame drop (wajib 60 FPS pada UI scrolling).

*Masalah Arsitektur:* Mengenkripsi ulang seluruh 50 GB saat rotasi kunci atau penghapusan memakan waktu terlalu lama dan merusak flash memory (wear leveling), sedangkan mengenkripsi file secara naif via software CryptoKit per blok memicu *thermal throttling* dan konsumsi baterai ekstrem.

**Pertanyaan Diagnostik & Solusi:**
1. Bagaimana arsitektur *Envelope Encryption* (Key Encryption Key / KEK yang disimpan di Secure Enclave vs. Data Encryption Key / DEK per file/blok) menyelesaikan dilema penghapusan instan (*cryptographic wipe*) dan rotasi kunci?
2. Bagaimana Anda mengeksploitasi arsitektur filesystem Apple (APFS) yang mendukung hardware-accelerated encryption dan *sparse files* untuk memastikan performa I/O baca-tulis 50 GB setara native speed tanpa *thermal throttling*?
3. Bagaimana mekanisme pengikatan KEK ke Secure Enclave dengan batasan kegagalan autentikasi (*hardware retry delay and lock-out*) agar brute-force hardware-level mustahil dilakukan?

---

## 4. Chapter Challenge

### Tantangan Praktis: Pembangunan Enterprise Hardened Crypto & Secure Enclave Vault Engine

#### Problem Statement
Sebuah institusi pertahanan membutuhkan modul core iOS (`EnterpriseSecurityVault.framework`) zero-dependency pihak ketiga untuk mengelola kredensial identitas, penandatanganan dokumen digital, dan penyimpanan payload sensitif secara offline pada perangkat high-risk.

#### Requirements
1. **Secure Enclave Signature Provider:**
   - Bangkitkan pasangan kunci Private/Public ECC NIST P-256 di dalam hardware Secure Enclave.
   - Enforce biometrik wajib (`.biometryCurrentSet`) menggunakan `SecAccessControl` sehingga penambahan sidik jari/wajah baru pada sistem iOS akan otomatis menginvalidasi kunci yang ada secara kriptografis.
   - Sediakan fungsi untuk menandatangani *digest* SHA-256 dengan private key Secure Enclave dan mengekspor public key dalam format ANSI X9.63 / DER.
2. **Volatile Memory Scrubber (`SecureBytes`):**
   - Buat tipe struktur data aman bertaraf low-level (`SecureBytes`) yang mengalokasikan memory via page-aligned system call (`posix_memalign`), mengunci halaman di RAM (`mlock`) agar tidak di-page out ke swap disk, dan membersihkan memory secara deterministik (`memset_s`) saat deinisialisasi (`deinit`).
3. **Envelope Encryption Engine:**
   - Implementasikan fungsi enkripsi simetris menggunakan `CryptoKit.AES.GCM` atau `ChaChaPoly`.
   - DEK (Data Encryption Key) digenerate per transaksi enkripsi secara random (kriptografis CSPRNG via `SecRandomCopyBytes`).
   - KEK (Key Encryption Key) dilindungi menggunakan kunci SEP atau Keychain dengan atribut `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`.
4. **Runtime Integrity Guard:**
   - Sediakan mekanisme validasi sebelum operasi kriptografi dijalankan: deteksi ptrace injection, pemeriksaan flag dynamic linker, dan pemeriksaan integritas bundle signing (`SecCodeCheckValidity`). Jika integritas gagal, kunci lokal harus di-purge seketika.

#### Constraints
- **Pure Swift & Native Frameworks:** Wajib hanya menggunakan Swift standar, `Security`, `CryptoKit`, `LocalAuthentication`, dan `Darwin/POSIX` C APIs. Dilarang keras menggunakan library pihak ketiga (No OpenSSL, No CryptoSwift).
- **Concurrency Safety:** Seluruh vault engine harus thread-safe, dirancang menggunakan model `actor` modern Swift 6 strict concurrency compliance (`Sendable`).
- **Zero Heap Residue:** Tidak boleh ada materi plain-text (kunci, payload rahasia) yang tertinggal di autoreleasepool atau heap memory setelah eksekusi fungsi enkripsi/dekripsi selesai.

#### Expected Output
1. File implementasi `SecureBytes.swift` (Memory-safe data container).
2. File implementasi `SecureEnclaveVaultActor.swift` (Enclave & Keychain manager dengan Swift Concurrency).
3. File implementasi `RuntimeIntegrityChecker.swift` (Integritas lingkungan & anti-tampering hook).
4. Unit tests lengkap yang memvalidasi:
   - Invalidasi kunci otomatis saat kondisi biometrik dimanipulasi/berubah.
   - Verifikasi bahwa signing payload berhasil divalidasi oleh public key menggunakan `CryptoKit`.
   - Pembersihan buffer memory (`SecureBytes`) menghasilkan byte `0x00` setelah deallokasi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Secure Enclave Processor (SEP), mailbox communication, dan isolasi perangkat keras dari Application Processor (AP).
- [ ] Siklus hidup kunci enkripsi pada iOS Data Protection API (Class A, B, C, D) dan integrasinya dengan status layar perangkat (Lock/Unlock).
- [ ] Perbedaan antara verifikasi biometrik software (LocalAuthentication boolean) dan evaluasi token kriptografis hardware via Keychain Access Control Lists.
- [ ] Kelemahan struktural mode cipher warisan (ECB, CBC) dan keunggulan keamanan algoritma AEAD (AES-GCM, ChaCha20-Poly1305) dalam mencegah tampering ciphertext.
- [ ] Titik injeksi serangan Man-In-The-Middle (MITM) pada TLS pipeline dan cara kerja Public Key Pinning (SPKI SHA-256) pada tingkat socket/transport layer.
- [ ] Dampak Automatic Reference Counting (ARC) terhadap residu materi kriptografi di heap memory dan cara kerja swap memory iOS.
- [ ] Vektor serangan runtime manipulation (Frida, Cycript, Substrate) dan batasan efektivitas deteksi jailbreak berbasis user-space.

### Saya tidak perlu menghafal:
- [ ] Struktur byte detail dari format spesifikasi ASN.1/DER untuk sertifikat X.509 dan public key encoding.
- [ ] Nilai konstanta heksadesimal mentah dari error code C-Security framework (misal: `-25300` untuk `errSecItemNotFound`).
- [ ] Algoritma internal polinomial Galois Counter Mode (GCM) GHASH secara matematis.
- [ ] Urutan exact opcodes assembly instruksi ARM64 untuk pemanggilan software interrupt syscall.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan pembacaan dan penulisan Keychain menggunakan `Security` framework API dengan flag keamanan terketat (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` dan `SecAccessControl`).
- [ ] Mengenerate pasangan kunci ECC di dalam Secure Enclave dan melakukan digital signing yang divalidasi biometrik secara thread-safe.
- [ ] Mengembangkan custom trust evaluation pada `URLSessionDelegate` untuk melakukan Public Key Pinning (SPKI) tanpa bergantung pada library pihak ketiga.
- [ ] Mengalokasikan, mengunci (`mlock`), dan membersihkan (`memset_s`) unmanaged memory buffer di Swift untuk data bernilai tinggi guna mitigasi memory dump forensics.
- [ ] Mengonfigurasi arsitektur Data Protection pada level file dan direktori database menggunakan `FileManager.setAttributes` secara terstruktur.
- [ ] Menyusun strategi isolasi antarmuka dan sanitasi visual untuk mengamankan data pengguna saat aplikasi memasuki background execution mode.