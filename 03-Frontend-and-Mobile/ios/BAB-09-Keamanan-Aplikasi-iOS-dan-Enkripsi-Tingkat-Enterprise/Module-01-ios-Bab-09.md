# Keamanan Aplikasi iOS & Enkripsi Tingkat Enterprise

---

## SEKSI 01 — IDENTITAS MODUL

* **Track/Domain:** 03-Frontend-and-Mobile
* **Kurikulum:** iOS Engineering
* **Bab:** 09 (Security, Cryptography, and Enterprise Hardening)
* **Modul:** 01
* **Topik:** Keamanan Aplikasi iOS & Enkripsi Tingkat Enterprise
* **Level Teknis:** Advanced / Staff Engineer
* **Prasyarat Pengetahuan:** 
  * Pemahaman mendalam tentang Swift Concurrency (`async`/`await`, `Sendable`, `Actor`).
  * Pengetahuan arsitektur memori iOS (Stack, Heap, Buffer, Pointers, Virtual Memory Pages).
  * Pengalaman menggunakan Security Framework (`Security.framework`) dan CryptoKit.
  * Pemahaman protokol jaringan TLS 1.3, X.509 Public Key Infrastructure (PKI), dan XPC.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, engineer diharapkan mampu:

1. **Mengonstruksi Arsitektur Zero-Trust di Perangkat:** Mendesain sistem penyimpanan data lokal dengan isolasi kriptografis penuh menggunakan Secure Enclave Processor (SEP), Keychain Services API, dan Data Protection Classes.
2. **Mengeksekusi Kriptografi Modern Standar Enterprise:** Mengimplementasikan enkripsi terotentikasi (Authenticated Encryption with Associated Data - AEAD) menggunakan AES-GCM-256 dan ChaCha20-Poly1305 via CryptoKit, serta manajemen kunci asimetris Curve25519 dan P-256.
3. **Membangun Pertahanan Transport Layer Anti-Tamper:** Mengembangkan pipeline `URLSession` dengan Custom Certificate & Public Key Pinning (HPKP modern) terisolasi, parsing Subject Public Key Info (SPKI), validasi Certificate Transparency (CT), dan revocations (CRLs/OCSP Stapling).
4. **Mendeteksi Kompromi Sistem Runtime:** Membangun engine deteksi Jailbreak, Dynamic Instrumentation (Frida/Cydia Substrate), Hooking (Method Swizzling/Dobby), dan debugger attachment (ptrace/sysctl) berbasis C-level Mach system calls.
5. **Mitigasi Serangan Memori:** Mencegah Memory Dumping dan Cold Boot Attacks dengan alokasi aman (`mlock`, `memset_s`, secure zeroing) serta mitigasi runtime metadata leak.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Zero Trust pada Lingkungan Klien
Sebagian besar engineer mobile salah mengasumsikan bahwa perangkat pengguna adalah komputasi tepercaya (*trusted compute environment*). Mental model enterprise mewajibkan prinsip: **Klien iOS adalah lingkungan yang sepenuhnya dikompromikan (Hostile Environment).**

```
+-----------------------------------------------------------------------+
|                         HOSTILE ENVIRONMENT                           |
|  +-----------------------------------------------------------------+  |
|  | User Space: Frida Hooks, Substrate, Cycript, Custom LLDB Attach |  |
|  +-----------------------------------------------------------------+  |
|  | Kernel Space: Jailbreak exploits, tfp0/tfpzero, root privileges |  |
|  +-----------------------------------------------------------------+  |
|  | Network: Malicious Proxies, Burp Suite, Rogue MitM Gateways     |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                    HARDENED APPLICATION ISOLATION                     |
|  +--------------------+  +--------------------+  +-----------------+  |
|  | Secure Memory Zone |  |  CryptoKit (AES)   |  | Integrity Core  |  |
|  | (mlock/zeroing)    |  |  + Hardware KEK    |  | (Mach/Sysctl)   |  |
|  +--------------------+  +--------------------+  +-----------------+  |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|               APPLE HARDWARE ROOT OF TRUST (TRUTH BASE)               |
|  +-----------------------------------------------------------------+  |
|  | Secure Enclave Processor (SEP) - Isolated Hardware Key Engine  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

1. **Semua yang Berada di RAM Adalah Terbuka:** String, auth token, dan kunci privat yang dialokasikan di Swift heap standar dapat dibaca melalui memory dump jika debugger/jailbreak aktif.
2. **ObjC Runtime Rentan Manipulasi:** Penggunaan method dynamic dispatching (`dynamic`, `@objc`) memudahkan attacker melakukan patch logika bisnis hanya dalam satu baris skrip Frida (`Interceptor.replace`).
3. **Defense in Depth (Pertahanan Berlapis):** Kriptografi software tidak cukup; kunci proteksi utama harus ditambatkan secara hardware melalui Key Encryption Keys (KEK) yang dihasilkan dan tidak pernah meninggalkan Secure Enclave Processor.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur otentikasi, enkripsi, dan transmisi data enterprise tingkat tinggi:

```
[ Swift Application Layer ]
             │
             ▼
[ Secure Enclave Processor (SEP) ]
   ├─► Cek Biometrik (LocalAuthentication / TouchID / FaceID)
   ├─► Akses Hardware-bound Key (ec256 / SecureEnclave.P256)
   └─► Menghasilkan Ephemeral Symmetric Key via ECDH
             │
             ▼
[ CryptoKit / Security.framework Engine ]
   ├─► Data Protection Class: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
   ├─► Enkripsi Payload: AES-GCM (256-bit Key, 96-bit Nonce, 128-bit Auth Tag)
   └─► Zeroing buffer plaintext via memset_s
             │
             ▼
[ Transport Security: Custom URLSession Layer ]
   ├─► System TLS 1.3 Handshake
   ├─► URLSessionDelegate: SecTrustEvaluateWithError
   ├─► Ekstraksi SPKI (Subject Public Key Info) SHA-256 Hash
   └─► Bandingkan dengan Hardcoded SPKI Pins (Pinning Assertion)
             │
             ▼
      [ Secure Network ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Data Protection API & iOS Keychain
Sistem operasi iOS mengimplementasikan enkripsi storage berbasis hardware melalui hierarki kunci:
* **Hardware UID:** Nilai unik yang di-*burn-in* ke dalam Secure Enclave silicon saat manufaktur. Tidak dapat dibaca oleh perangkat lunak, sistem operasi, bahkan oleh Apple.
* **Passcode-Derived Key:** Dihasilkan via PBKDF2 dari PIN/Passcode pengguna.
* **Class Key:** Didelegasikan berdasarkan Accessibility Attributes:
  * `kSecAttrAccessibleAlways` (*Deprecated & Insecure*): Kunci didekripsi menggunakan UID saja.
  * `kSecAttrAccessibleAfterFirstUnlock`: Kunci dipertahankan di RAM setelah perangkat dibuka pertama kali pasca-reboot.
  * `kSecAttrAccessibleCompleteUntilFirstUserAuthentication`: Ideal untuk proses background sync.
  * `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`: Didekripsi hanya saat perangkat aktif terbuka. Kunci ditolak untuk migrasi via iCloud Backup atau pemindahan antar-perangkat via image restore.

### 2. Secure Enclave Processor (SEP)
SEP adalah sub-sistem SoC tersendiri yang menjalankan microkernel (L4-family) terpisah dari CPU Application (Apple Silicon Core). SEP menangani:
* Hardware Random Number Generator (TRNG).
* AES Engine mandiri (Side-Channel Attack Resistant).
* Penyimpanan Secure Enclave Key: Kunci privat asimetris kurva eliptik P-256 tidak pernah terekspos ke kernel iOS Application Processor (AP). AP hanya mengirimkan pesan ke SEP melalui shared mailboxes untuk meminta operasi: "Tolong tanda tangani SHA-256 hash ini" atau "Lakukan key exchange ECDH dengan public key remote ini".

### 3. Subject Public Key Info (SPKI) Pinning
Berbeda dengan Certificate Pinning biasa (yang menyematkan seluruh berkas sertifikat X.509 dan akan gagal ketika sertifikat kadaluarsa dan diperbarui oleh CA), SPKI Pinning mengekstrak byte kunci publik murni dari ASN.1 structure:
1. Dapatkan referensi `SecTrust` dari TLS handshake.
2. Dapatkan `SecKey` dari public key leaf certificate server.
3. Serialisasi `SecKey` ke representasi DER/PKCS#1, ambil block bytes SPKI.
4. Hitung `SHA256(spki_bytes)`.
5. Bandingkan base64-encoded SHA-256 hash terhadap pre-shared public key hash enterprise. 

Pembaruan sertifikat dengan CSR (Certificate Signing Request) yang sama akan mempertahankan SPKI hash yang identik, mencegah downtime pembaruan sertifikat.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Authenticated Encryption with Associated Data (AEAD)
Enkripsi mode cipher lama seperti AES-CBC rentan terhadap serangan manipulasi bit (*bit-flipping*) dan padding oracle (*Vaudenay attacks*). AES-GCM (Galois/Counter Mode) mengatasi masalah ini dengan menyediakan kerahasiaan (*confidentiality*) dan keabsahan (*authenticity*) secara bersamaan.

$$\text{Ciphertext}, \text{Tag} = \text{AES-GCM-Encrypt}(K, IV, P, AAD)$$

Komponen:
* **$K$ (Symmetric Key):** 256 bits (32 bytes).
* **$IV$ (Initialization Vector / Nonce):** 96 bits (12 bytes). Mutlak tidak boleh digunakan ulang dengan kunci yang sama. Penggunaan ulang nonce pada GCM meruntuhkan seluruh jaminan keamanan GHASH dan membuka kunci private.
* **$P$ (Plaintext):** Payload data sensitif.
* **$AAD$ (Additional Authenticated Data):** Data tambahan yang tidak dienkripsi namun terikat secara integritas ke Authentication Tag (misal: Device ID, Request Headers, Timestamp).
* **$\text{Tag}$:** 128 bits (16 bytes) nilai GHASH untuk memverifikasi bahwa ciphertext dan AAD belum dimanipulasi di transit.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah modul fundamental enkripsi simetris enterprise memanfaatkan `CryptoKit` dengan zeroing memory buffer:

```swift
import Foundation
import CryptoKit

public final class EnterpriseCryptoEngine {
    
    public enum CryptoError: Error {
        case encryptionFailed
        case decryptionFailed
        case authenticationTagMismatch
        case invalidKeySize
    }

    /// Melakukan enkripsi data sensitif menggunakan AES-GCM 256-bit dengan AAD
    public static func encrypt(
        plaintext: Data,
        symmetricKey: SymmetricKey,
        authenticatedData: Data = Data()
    ) throws -> (ciphertext: Data, tag: Data, nonce: Data) {
        do {
            // Generate single-use CSPRNG 96-bit Nonce
            let nonce = AES.GCM.Nonce()
            
            // Eksekusi AES-GCM Seal
            let sealedBox = try AES.GCM.seal(
                plaintext,
                using: symmetricKey,
                nonce: nonce,
                authenticating: authenticatedData
            )
            
            return (
                ciphertext: sealedBox.ciphertext,
                tag: sealedBox.tag,
                nonce: Data(nonce)
            )
        } catch {
            throw CryptoError.encryptionFailed
        }
    }

    /// Melakukan dekripsi dan verifikasi integritas data
    public static func decrypt(
        ciphertext: Data,
        symmetricKey: SymmetricKey,
        nonceData: Data,
        tag: Data,
        authenticatedData: Data = Data()
    ) throws -> Data {
        do {
            let nonce = try AES.GCM.Nonce(data: nonceData)
            let sealedBox = try AES.GCM.SealedBox(
                nonce: nonce,
                ciphertext: ciphertext,
                tag: tag
            )
            
            let decryptedData = try AES.GCM.open(
                sealedBox,
                using: symmetricKey,
                authenticating: authenticatedData
            )
            
            return decryptedData
        } catch {
            throw CryptoError.decryptionFailed
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

1. `let nonce = AES.GCM.Nonce()`: Memanfaatkan CryptoKit internal provider untuk memanggil secure random bytes dari kernel `/dev/urandom`. Nilai ini unik per enkripsi, mencegah replay attack dan ciphertext deduplication analysis.
2. `try AES.GCM.seal(plaintext, using: symmetricKey, nonce: nonce, authenticating: authenticatedData)`: Memanggil hardware acceleration via AES-NI / Apple Silicon Crypto Engine. Parameter `authenticating` menyertakan AAD yang akan dihitung ke dalam kalkulasi GHASH tag tanpa dienkripsi ke dalam ciphertext.
3. `let sealedBox = try AES.GCM.SealedBox(...)`: Merekonstruksi payload kriptografi dari 3 komponen terpisah (*nonce*, *ciphertext*, *tag*).
4. `try AES.GCM.open(...)`: Melakukan dekripsi konstan-waktu (*constant-time*). Jika nilai $AAD$ atau $Ciphertext$ diubah bahkan sebanyak 1 bit saja, autentikasi tag gagal dan method seketika melemparkan eksepsi, mencegah *unauthenticated plaintext leakage*.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Insiden Produksi: Financial Banking Trojan Injection
Sebuah aplikasi Digital Banking Tier-1 menghadapi serangan terkoordinasi:
* Attacker menggunakan tweak framework modern (Shadow/Choicy + Frida) pada perangkat iOS yang di-jailbreak untuk melewati sistem otentikasi biometrik standar.
* Attacker melakukan hooking pada kelas `LAContext.evaluatePolicy` via Objective-C runtime swizzling, memalsukan response menjadi `(true, nil)`.
* Attacker mengekstraksi API authorization tokens yang disimpan di `UserDefaults` dan `kSecAttrAccessibleAlways` Keychain, lalu menduplikasi session untuk menguras saldo tabungan melalui automated API scripting.

### Kebutuhan Solusi
1. **Hardware-bound Auth:** Menghilangkan token berbasis software murni. Kunci otentikasi wajib dikunci di Secure Enclave dengan `SecAccessControl` yang meminta validasi biometrik langsung di level hardware microkernel SEP.
2. **Dynamic Runtime Integrity Engine:** Deteksi jailbreak multilapis via direct C-syscalls (`syscall(SYS_read...)`), pengecekan integritas binary Text Segment dyld (`__TEXT, __text`), dan debugger check via `sysctl`.
3. **Network Layer Lock:** Memblokir seluruh proxy man-in-the-middle melalui Custom URLSession SPKI Pinning.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi komprehensif yang memadukan Secure Enclave Manager, Runtime Anti-Tamper Engine, dan SPKI Pinning Engine.

### 1. Secure Enclave Cryptographic Key Engine

```swift
import Foundation
import Security
import LocalAuthentication
import CryptoKit

public final class SecureEnclaveVault {
    public static let shared = SecureEnclaveVault()
    private let keyTag = "com.enterprise.vault.sepKey".data(using: .utf8)!

    private init() {}

    /// Membuat atau mengambil Secure Enclave P-256 Private Key
    public func retrieveOrCreateHardwareKey() throws -> SecureEnclave.P256.KeyAgreement.PrivateKey {
        // Cek dukungan ketersediaan SEP pada SoC perangkat
        guard SecureEnclave.isAvailable else {
            throw VaultError.secureEnclaveUnavailable
        }

        // Tentukan aturan proteksi hardware-bound dengan UserPresence (Biometric / Passcode)
        var error: Unmanaged<CFError>?
        guard let accessControl = SecAccessControlCreateWithFlags(
            kCFAllocatorDefault,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            [.privateKeyUsage, .biometryCurrentSet],
            &error
        ) else {
            throw VaultError.accessControlCreationFailed(error?.takeRetainedValue())
        }

        // Cek apakah kunci sudah terdaftar di Keychain
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: keyTag,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecReturnRef as String: true
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)

        if status == errSecSuccess, let secKey = item as! SecKey? {
            // Rekonstruksi CryptoKit representation dari SecKey
            return try SecureEnclave.P256.KeyAgreement.PrivateKey(secKey: secKey)
        } else if status == errSecItemNotFound {
            // Buat kunci baru langsung di dalam Secure Enclave
            let authContext = LAContext()
            authContext.touchIDAuthenticationAllowableReuseDuration = 0 // Strict context
            
            let privateKey = try SecureEnclave.P256.KeyAgreement.PrivateKey(
                accessControl: accessControl,
                authenticationContext: authContext
            )
            
            // Simpan referensi ke Keychain
            let addQuery: [String: Any] = [
                kSecClass as String: kSecClassKey,
                kSecAttrApplicationTag as String: keyTag,
                kSecValueRef as String: privateKey.secKey!,
                kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            ]
            
            let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
            guard addStatus == errSecSuccess else {
                throw VaultError.keychainPersistenceFailed(addStatus)
            }
            return privateKey
        } else {
            throw VaultError.keychainQueryFailed(status)
        }
    }
}

public enum VaultError: Error {
    case secureEnclaveUnavailable
    case accessControlCreationFailed(CFError?)
    case keychainPersistenceFailed(OSStatus)
    case keychainQueryFailed(OSStatus)
}

extension SecureEnclave.P256.KeyAgreement.PrivateKey {
    var secKey: SecKey? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecValueData as String: self.dataRepresentation,
            kSecReturnRef as String: true
        ]
        var item: CFTypeRef?
        let status = SecItemAdd(query as CFDictionary, &item)
        if status == errSecSuccess || status == errSecDuplicateItem {
            return (item as! SecKey)
        }
        return nil
    }
    
    convenience init(secKey: SecKey) throws {
        var error: Unmanaged<CFError>?
        guard let data = SecKeyCopyExternalRepresentation(secKey, &error) as Data? else {
            throw error!.takeRetainedValue()
        }
        try self.init(dataRepresentation: data)
    }
}
```

### 2. Low-Level Mach & Sysctl Anti-Tamper Engine

```swift
import Foundation
import Darwin
import MachO

public final class RuntimeIntegrityEngine {
    
    /// Memverifikasi debugger via kernel process information flag
    public static func isDebuggerAttached() -> Bool {
        var info = kinfo_proc()
        var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
        var size = MemoryLayout<kinfo_proc>.stride
        
        let junk = sysctl(&mib, UInt32(mib.count), &info, &size, nil, 0)
        assert(junk == 0, "sysctl failed")
        
        // Cek P_TRACED flag di dalam kp_proc.p_flag
        return (info.kp_proc.p_flag & P_TRACED) != 0
    }

    /// Melakukan inspeksi sistem file dan symbolic links untuk deteksi jailbreak
    public static func evaluateJailbreakState() -> Bool {
        #if targetEnvironment(simulator)
        return false // Bypass validasi saat kompilasi ke local developer simulator
        #else
        let paths: [String] = [
            "/Applications/Cydia.app",
            "/Library/MobileSubstrate/MobileSubstrate.dylib",
            "/bin/bash",
            "/usr/sbin/sshd",
            "/etc/apt",
            "/usr/bin/ssh",
            "/private/var/lib/apt"
        ]
        
        for path in paths {
            if FileManager.default.fileExists(atPath: path) {
                return true
            }
        }
        
        // Uji kemampuan menulis ke luar Application Sandbox
        let testString = "JailbreakValidationProbe"
        let sandboxBreachPath = "/private/jailbreak_probe.txt"
        do {
            try testString.write(toFile: sandboxBreachPath, atomically: true, encoding: .utf8)
            try FileManager.default.removeItem(atPath: sandboxBreachPath)
            return true // Menulis di luar sandbox sukses = Device Jailbroken
        } catch {
            // Normal: Sandbox menolak operasi
        }
        
        // Periksa loaded dynamic libraries dari Dyld
        let dyldCount = _dyld_image_count()
        for i in 0..<dyldCount {
            if let rawImageName = _dyld_get_image_name(i) {
                let imageName = String(cString: rawImageName).lowercased()
                if imageName.contains("frida") ||
                   imageName.contains("cydiasubstrate") ||
                   imageName.contains("substitute") ||
                   imageName.contains("substrate") {
                    return true
                }
            }
        }
        
        return false
        #endif
    }
}
```

### 3. Subject Public Key Info (SPKI) Pinning Delegate

```swift
import Foundation
import Security
import CryptoKit

public final class EnterprisePinningDelegate: NSObject, URLSessionDelegate {
    
    private let validSPKIHashes: Set<String>
    
    public init(validSPKIHashes: Set<String>) {
        self.validSPKIHashes = validSPKIHashes
        super.init()
    }
    
    public func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        // Abaikan challenge jika bukan server trust authentication
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 1. Validasi Chain Standar RFC 5280
        var error: CFError?
        let isTrusted = SecTrustEvaluateWithError(serverTrust, &error)
        guard isTrusted else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 2. Ekstraksi Leaf Certificate (Indeks 0 pada Trust Chain)
        guard let certificateChain = SecTrustCopyCertificateChain(serverTrust) as? [SecCertificate],
              let leafCertificate = certificateChain.first else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 3. Ekstraksi Public Key
        guard let publicKey = SecCertificateCopyKey(leafCertificate) else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 4. Transformasi SecKey ke format SPKI Data
        var keyError: CFError?
        guard let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, &keyError) as Data? else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 5. Normalisasi SPKI Header (PKCS#1 vs X.509 ASN.1 wrap untuk RSA/ECC)
        // Hitung SHA-256 Digest dari representasi kunci publik
        let digest = SHA256.hash(data: publicKeyData)
        let digestBase64 = Data(digest).base64EncodedString()
        
        // 6. Evaluasi pin
        if validSPKIHashes.contains(digestBase64) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            // Pinning Verification Gagal
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Implementasi | Keychain Standar | Secure Enclave Processor (SEP) | Software AES-GCM (CryptoKit) |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Kunci** | SQLite db terenkripsi via OS UID key | Sub-sistem silikon terpisah, Non-volatile memory | RAM memori aplikasi biasa |
| **Ketahanan Hooking Frida** | Rendah (bisa memanipulasi parameter SecItemCopy) | Tinggi (kunci privat tidak berada di memori AP) | Menengah (kunci bisa terekspos via Heap scan) |
| **Throughput/Performa** | Menengah (~10ms) | Rendah jika pakai biometrik (~500ms), Tinggi per session | Sangat Cepat (Hardware Crypto Engine) |
| **Kapasitas Payload** | Maksimal 4KB per item | Maksimal ukuran 256-bit ECDH/ECDSA | Bebas (Streamable multi-gigabyte) |
| **Portabilitas Data** | Bisa di-backup ke iCloud jika tidak diberi flag `ThisDeviceOnly` | Tidak pernah bisa di-export atau ditransfer ke SoC lain | Tergantung enkripsi pembungkus kunci |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Invalidation Kunci Biometrik Saat Registrasi Ulang Wajah/Sidik Jari
* **Kegagalan:** Jika penyerang berhasil mendapatkan passcode iPhone, penyerang dapat mendaftarkan sidik jari atau *Alternative Appearance FaceID* mereka sendiri ke pengaturan iOS.
* **Mitigasi:** Gunakan access control flag `.biometryCurrentSet` saat pembuatan kunci di Secure Enclave. Jika pengguna menambah atau mengubah biometrik mereka, SEP akan seketika merusak/menolak (*invalidate*) kunci enkripsi tersebut. Data lama tidak dapat didekripsi lagi dan aplikasi wajib memaksa re-login kredensial utama.

### 2. Deadlock pada Main Thread Saat Mengakses Keychain
* **Kegagalan:** Mengakses Keychain API (`SecItemCopyMatching`) yang dilindungi biometrik pada Main Thread. Jika FaceID prompt muncul dan terinterupsi background task, watchdog OS (`springboard`) akan menghentikan paksa (*crash*) aplikasi dengan code `0x8badf00d` (ate bad food).
* **Mitigasi:** Eksekusi seluruh alur Secure Enclave dan Keychain IO di dalam dedicated background `Actor` atau `DispatchQueue(label: "enterprise.vault.io")`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Hardcoding Secret Key / IV di Binary
* **Kesalahan:** Menaruh kunci simetris `let encryptionKey = "MySuperSecretKey1234"` langsung di dalam kode Swift. Kunci ini dapat diekstraksi dalam hitungan detik menggunakan perintah command-line `strings YourApp.app/YourApp` atau Ghidra decompiler.
* **Solusi:** Jangan pernah menyimpan kunci statis di binary. Turunkan kunci dinamis dari Secure Enclave menggunakan pertukaran kunci Diffie-Hellman (ECDH) bersama server backend via ephemeral sessions.

### 2. Mengabaikan Sensitive Memory Sanitization
* **Kesalahan:** Bergantung penuh pada Automatic Reference Counting (ARC) untuk menghapus password atau pin dari memory. String di Swift di-*copy-on-write* dan didistribusikan di heap tanpa zeroization, meninggalkan sisa data (*memory remanence*) yang dapat dibaca lewat lldb memory dump.
* **Solusi:** Gunakan contiguous byte buffers (`UnsafeMutablePointer<UInt8>`) dan lakukan penghapusan manual menggunakan fungsi standar C `memset_s` segera setelah data selesai digunakan.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Cryptographic Agility:** Rancang abstraksi protocol-oriented untuk modul kriptografi sehingga migrasi dari Curve25519/AES-GCM ke Post-Quantum Cryptography (seperti ML-KEM/Kyber) di masa depan tidak merombak business logic aplikasi.
2. **Eliminasi String Literals Sensitif:** String sensitif seperti endpoint URL internal atau public key hashes harus dienkode menggunakan dynamic byte-obfuscation compile-time macros atau Swift packages (misal: XOR masking dengan compiler salt).
3. **Audit Keychain ACL:** Pastikan tidak ada satupun item Keychain enterprise yang menggunakan flag legacy `kSecAttrAccessibleAlways`. Standar baku wajib: `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` atau `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Secure In-Memory Buffer Erasure
Penggunaan `String` atau `Data` standar Swift rentan meninggalkan duplikasi memori saat mutasi. Implementasikan *Zero-Allocation Secure Data Wrapper*:

```swift
public final class SecureMemoryBlock {
    private var pointer: UnsafeMutablePointer<UInt8>
    public let size: Int

    public init(size: Int) {
        self.size = size
        self.pointer = UnsafeMutablePointer<UInt8>.allocate(capacity: size)
        self.pointer.initialize(repeating: 0, count: size)
        // Kunci alokasi memori ke physical RAM, cegah OS swapping ke disk swap file
        mlock(pointer, size)
    }

    public func accessBuffer(_ body: (UnsafeMutablePointer<UInt8>) -> Void) {
        body(pointer)
    }

    deinit {
        // Sanitasi memori: Timpa seluruh buffer dengan byte 0 menggunakan memset_s
        memset_s(pointer, size, 0, size)
        munlock(pointer, size)
        pointer.deallocate()
    }
}
```
* **Kompensasi Performa:** Penggunaan `mlock` mencegah sistem operasi menulis halaman memori yang berisi material kunci ke NAND Flash saat memory-pressure paging, menghindari disk-forensic leakage.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Runtime Anti-Hooking & Binary Stripping Checklist
1. **Disable Method Swizzling Vulnerabilities:** Hindari pewarisan dari `NSObject` dan kata kunci `dynamic` pada domain layer dan security layer. Buat seluruh struct dan final class untuk mematikan vtable/dynamic message dispatch (`objc_msgSend`).
2. **Enforce Symbols Stripping:**
   * Di Xcode Build Settings: Ubah `Deployment Postprocessing` ke `YES`.
   * Ubah `Strip Linked Product` ke `YES`.
   * Ubah `Strip Swift Symbols` ke `YES`.
   * Ubah `Symbols Display Level` ke `Hide All`.
3. **Anti-PTRACE Injection:**
   Sisipkan ptrace invocation saat runtime initialization untuk memutus kaitan software debugger:

```swift
#if !DEBUG
import Darwin

@inline(__always)
public func disableDebuggerTracing() {
    let ptracePtr = dlsym(dlopen(nil, RTLD_NOW), "ptrace")
    typealias PTraceType = @convention(c) (CInt, pid_t, CInt, CInt) -> CInt
    if let ptrace = ptracePtr {
        let ptraceFunc = unsafeBitCast(ptrace, to: PTraceType.self)
        // 31 melambangkan PT_DENY_ATTACH
        _ = ptraceFunc(31, 0, 0, 0)
    }
}
#endif
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Ketika mengimplementasikan sistem keamanan enterprise, *crash* yang disengaja akibat violation/integrity failure tidak boleh meninggalkan jejak log forensik yang mengekspos alasan keamanan kepada penyerang:

```swift
public enum EnterpriseSecurityMonitor {
    
    public static func reportSecurityViolation(event: SecurityAnomaly) {
        // Enkripsi payload telemetri sebelum dikirimkan
        let payload: [String: Any] = [
            "anomaly_type": event.rawValue,
            "timestamp": Date().timeIntervalSince1970,
            "device_id": getHashedDeviceIdentifier()
        ]
        
        // Transmisi Out-Of-Band melalui dedicated isolated endpoint
        DispatchQueue.global(qos: .utility).async {
            sendEncryptedTelemetry(payload)
            
            #if !DEBUG
            // Terminate proses seketika dengan assembly invalid opcode
            // Tidak menggunakan fatalError() karena meninggalkan pesan di stack dump
            Darwin.exit(EXIT_FAILURE)
            #endif
        }
    }
}

public enum SecurityAnomaly: String {
    case debuggerDetected = "ERR_DBG_ATTACHED"
    case jailbreakCompromised = "ERR_JB_FLAG_SET"
    case pinValidationFailed = "ERR_TLS_SPKI_MISMATCH"
}

private func getHashedDeviceIdentifier() -> String {
    // Generate stateless ephemeral hardware hash
    return "DEVICE_HASH_PSEUDO"
}

private func sendEncryptedTelemetry(_ payload: [String: Any]) {
    // Background POST via ephemeral URLSession
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

1. **Algoritma Simetris:** Gunakan hanya **AES-GCM** (256-bit) atau **ChaCha20-Poly1305**. Hindari CBC atau ECB.
2. **Kunci Hardware:** Gunakan `SecureEnclave.P256.KeyAgreement` dengan access flags `.biometryCurrentSet`.
3. **Keychain Accessibility:** Wajib diset minimal ke `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`. Jangan pernah sertakan fallback iCloud Sync untuk data credential.
4. **Transport Layer Security:** Tinggalkan Full-Cert pinning, gunakan **SPKI SHA-256 Pinning** di dalam `URLSessionDelegate`.
5. **Memory Zeroing:** Variabel penampung plaintext tidak boleh dibiarkan ter-deallokasi oleh ARC secara implisit; manfaatkan `mlock` dan `memset_s`.
6. **Anti-Tampering:** Kombinasikan verifikasi `sysctl P_TRACED`, dyld image inspection, dan syscall direct checking untuk mendeteksi instrumen dinamis seperti Frida.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa Subject Public Key Info (SPKI) Pinning lebih direkomendasikan untuk aplikasi enterprise skala besar dibandingkan Full Certificate Pinning?
* A) Karena SPKI pinning memverifikasi validitas CRL jauh lebih cepat daripada full cert.
* B) Karena SPKI pinning mengekstrak representasi hash kunci publik murni, memungkinkan pembaruan/rotasi sertifikat X.509 server tanpa memicu insiden downtime aplikasi, asalkan pasangan keypair server