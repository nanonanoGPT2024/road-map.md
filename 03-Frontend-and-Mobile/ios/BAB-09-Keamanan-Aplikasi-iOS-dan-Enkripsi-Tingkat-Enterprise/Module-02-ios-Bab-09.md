# BAB 09: Keamanan Aplikasi iOS dan Enkripsi Tingkat Enterprise
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Hardware-Backed Security** menggunakan Apple Secure Enclave Processor (SEP) dan CryptoKit untuk manajemen kunci asimetris tingkat perangkat keras.
- **Merancang Sistem Autentikasi Kriptografis Zero-Trust** berbasis biometrik (`LocalAuthentication`) yang kebal terhadap pembajakan runtime dan serangan pergantian biometrik lokal (`biometryCurrentSet`).
- **Mengembangkan Layer Jaringan Terproteksi Tingkat Tinggi** dengan Dynamic Public Key Pinning (SPKI SHA-256) dan Mutual TLS (mTLS) berbasis sertifikat klien yang di-generate langsung dari dalam Secure Enclave.
- **Mengimplementasikan Runtime Application Self-Protection (RASP)** komprehensif, mencakup deteksi Jailbreak berlapis (kernel-level/syscall, filesystem, dyld inspection), anti-debugging (`sysctl`, `ptrace`), anti-tampering, dan pendeteksian injection framework (Frida, Substrate, Cycript).
- **Mengelola Mitigasi Risiko Kriptografis Enterprise** dengan merancang arsitektur rotasi sertifikat/kunci darurat (*disaster recovery cert rollover*) tanpa memerlukan rilis darurat ke App Store.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Arsitektur Sistem Operasi iOS**: Pemahaman mendalam tentang Mach-O binary format, dynamic linker (`dyld`), POSIX system calls, sandboxing model iOS, dan iOS Application Lifecycle.
- **Fondasi Kriptografi**: Pemahaman praktis mengenai Symmetric Encryption (AES-GCM, ChaCha20-Poly1305), Asymmetric Cryptography (NIST P-256, Curve25519), Message Authentication Codes (HMAC), dan X.509 Certificate Parsing (ASN.1 structure).
- **Swift 6 & Modern iOS Development**: Penguasaan concurrency model Swift (`async/await`, `actor`, `Sendable`), Core Foundation memory management (`Unmanaged`, `CFRelease`), serta framework `CryptoKit` dan `Security.framework`.
- **Environment Kerja**:
  - Mac dengan Apple Silicon (M1/M2/M3/M4) untuk native hardware simulation.
  - Xcode 16+ dengan iOS 18 SDK.
  - Perangkat Fisik iPhone (wajib, bukan Simulator) dengan Secure Enclave dan Face ID/Touch ID aktif untuk pengetesan hardware security.
  - Proxy Interception tools (Charles Proxy, mitmproxy, atau Burp Suite Enterprise) untuk simulasi Man-in-the-Middle (MITM).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Secure Enclave Processor (SEP) Internal Architecture
Secure Enclave adalah co-processor komputasi terisolasi yang diintegrasikan ke dalam Apple Silicon SoCs (mulai dari A7 dan Apple M-series). SEP beroperasi secara independen dari Application Processor (AP) utama yang menjalankan iOS Kernel.

```
+-----------------------------------------------------------------------+
|                             Apple SoC                                 |
|                                                                       |
|  +--------------------------------+   +----------------------------+  |
|  |     Application Processor      |   |   Secure Enclave (SEP)     |  |
|  |            (AP)                |   |                            |  |
|  |                                |   | +------------------------+ |  |
|  |  +--------------------------+  |   | | Secure OS (sePOS)      | |  |
|  |  | User Space: iOS Apps     |  |   | +------------------------+ |  |
|  |  +--------------------------+  |   | | TRNG (Hardware Random) | |  |
|  |  | Kernel Space: XNU Kernel |  |   | +------------------------+ |  |
|  |  +--------------------------+  |   | | Hardware AES Engine    | |  |
|  |               |                |   | +------------------------+ |  |
|  |               | (IOSharedData) |   | | Secure Memory (TZ0)    | |  |
|  |               v                |   | +------------------------+ |  |
|  |      [ Mailbox Interface ]     |   |              ^             |  |
|  +---------------|----------------+   +--------------|-------------+  |
|                  |                                   |                |
|                  +======== Hardened Bridge ==========+                |
|                                                                       |
|  +------------------------------------+                               |
|  |  Device Unique Key (UID) - Fused   | (Direct Hardwired to SEP AES) |
|  +------------------------------------+                               |
+-----------------------------------------------------------------------+
```

1. **Hardware Isolation**: SEP memiliki mikrokernel tersendiri (*sePOS*), Secure Memory (terproteksi enkripsi hardware on-the-fly via memory controller TZ0), dan True Random Number Generator (TRNG) berbasis hardware.
2. **Device Unique ID (UID)**: Kunci AES-256 yang di-burn ke dalam e-fuses chip saat manufaktur. UID tidak dapat dibaca oleh software, iOS Kernel, maupun Apple. Enkripsi/dekripsi berbasis hardware menggunakan UID langsung diproses oleh Hardware AES Engine di dalam SEP.
3. **Mailbox Protocol**: AP dan SEP berkomunikasi menggunakan memori bersama berbasis antrian interrupt yang disebut *Mailbox*. AP mengirim instruksi (misal: "tanda tangani hash ini menggunakan Private Key ID: 0x4F1B"). SEP memverifikasi kondisi otorisasi (apakah Face ID lolos?), memproses operasi kriptografi di dalam ruang isolasinya, dan hanya mengembalikan signature atau ciphertext ke AP. **Private Key tidak pernah keluar dari batas fisik SEP**.
4. **Access Control Flags**:
   - `.biometryAny`: Kunci dapat diakses jika biometrik apapun yang terdaftar lolos verifikasi.
   - `.biometryCurrentSet`: Kunci diikat secara kriptografis ke database biometrik saat kunci dibuat. Jika user menambah, menghapus, atau mendaftarkan ulang jari/wajah di iOS Settings, kunci SEP tersebut secara otomatis rusak permanen (*invalidated*).

#### 3.2. Public Key Pinning: SPKI Hashing vs Certificate Pinning
Implementasi pinning konvensional berbasis sertifikat penuh (`.cer` / `.der`) memiliki tingkat kerapuhan operasional tinggi: ketika Leaf Certificate kedaluwarsa atau dirotasi oleh tim DevOps, aplikasi akan crash atau gagal terhubung secara serentak ke API.

Enterprise architecture mengadopsi **Subject Public Key Info (SPKI) SHA-256 Pinning**:

```
+------------------------------------------------------------------+
|                    X.509 Digital Certificate                     |
|                                                                  |
|  [ TBSCertificate (To Be Signed) ]                               |
|    - Version, Serial Number, Signature Algorithm                 |
|    - Issuer Name, Validity Period, Subject Name                 |
|    - SubjectPublicKeyInfo (SPKI)  <--- PINNED TARGET ONLY!       |
|      +-- AlgorithmIdentifier (e.g., id-ecPublicKey)              |
|      +-- BitString SubjectPublicKey (Public Key Material)        |
|  [ SignatureAlgorithm ]                                          |
|  [ SignatureValue ]                                              |
+------------------------------------------------------------------+
                                  |
                                  v
                        [ SHA-256 Hashing ]
                                  |
                                  v
               Base64 Hash: "YLh1dUR9y6Kja30AzZxVgGF..."
```

Dengan mengabaikan field sertifikat yang sering berubah (validity period, serial number, signature metadata) dan hanya mengekstrak serta menghash byte array ASN.1 dari `SubjectPublicKeyInfo`, enterprise dapat melakukan rotasi sertifikat TLS menggunakan Private Key yang sama (CSR recycling) tanpa perlu merilis pembaruan biner aplikasi ke App Store.

#### 3.3. RASP (Runtime Application Self-Protection) Deep Dive
Aplikasi finansial dan enterprise berjalan di lingkungan *zero-trust* (perangkat pengguna yang mungkin disusupi). RASP memitigasi serangan dinamis melalui deteksi berlapis:
1. **Dynamic Linker (`dyld`) Inspection**: Memvalidasi seluruh image/library yang dimuat ke dalam virtual memory address space untuk mendeteksi inject library berbahaya (`MobileSubstrate`, `FridaGadget.dylib`, `CydiaSubstrate`, `SSLUnpinning.dylib`).
2. **Anti-Debugging via POSIX & Mach Interfaces**: Memanfaatkan flag kernel `PT_DENY_ATTACH` melalui pointer `ptrace` native, serta inspeksi status tracing kernel via `sysctl` (`P_TRACED`).
3. **Low-level Syscall vs Sandboxing Validation**: Memeriksa pelanggaran sandbox iOS dengan mencoba memanggil syscalls yang seharusnya dilarang (misal: `fork()`, penulisan ke path di luar sandbox seperti `/private/jailbreak.txt`, atau keberadaan symlink `/Applications`).

---

### 4. Why & What

| Vektor Keamanan | Mengapa Penting di Skala Enterprise? | Apa yang Harus Diimplementasikan? |
| :--- | :--- | :--- |
| **Penyimpanan Kredensial & Kunci Sesi** | Jika AP disusupi root exploit, data di RAM dan disk dapat diekstrak. Software-only AES mudah dibobol via memory dump. | Kunci autentikasi sesi privat wajib di-generate dan disimpan di **Secure Enclave** dengan otorisasi `.biometryCurrentSet`. |
| **Komunikasi Jaringan (MITM Attacks)** | Proksi perusahaan jahat, rogue Wi-Fi, atau compromised Public CAs dapat memalsukan sertifikat TLS dan mendekripsi trafik. | **SPKI SHA-256 Pinning** dengan Fallback Backup Key + **Mutual TLS (mTLS)** berbasis hardware-backed client certificate. |
| **Runtime Tampering & Reverse Engineering** | Attacker menggunakan Frida untuk mem-bypass autentikasi lokal, SSL pinning, atau memanipulasi return value method perbankan. | **Multi-layer RASP**: Direct syscall execution, memory integrity checks, continuous Mach-O binary section checksumming. |
| **Kehilangan/Pencurian Perangkat** | Penyerang fisik yang memaksa pendaftaran sidik jari tambahan untuk membobol proteksi aplikasi perbankan. | Deteksi mutasi State Database Biometrik lokal menggunakan evaluasi `evaluatedPolicyDomainState`. |

---

### 5. How (Workflow Detail)

#### Workflow 1: Pendaftaran & Penggunaan Hardware-Backed Key
1. Klien menginisialisasi pembuatan pasangan kunci asimetris NIST P-256 via CryptoKit / Security Framework.
2. Parameter `kSecAttrTokenIDSecureEnclave` disematkan bersama `SecAccessControl` yang mewajibkan otorisasi biometrik pengguna.
3. Kunci publik diekstrak dan dikirim ke Enterprise Identity Provider (IdP) bersamaan dengan payload pendaftaran perangkat.
4. Saat autentikasi transaksi:
   - Server mengirimkan cryptographic challenge (32-byte cryptographically secure random nonce).
   - Aplikasi meminta SEP menandatangani (*sign*) nonce tersebut.
   - Sistem operasi iOS secara otomatis memicu UI Face ID/Touch ID dari level kernel (Out-of-Band display hardware).
   - SEP memverifikasi biometrik; jika valid, SEP mengeksekusi ECDSA Signature pada nonce dan mengembalikannya ke aplikasi.
   - Server memverifikasi signature menggunakan kunci publik yang telah terdaftar.

#### Workflow 2: Validasi SPKI Pinning Jaringan
1. Aplikasi mengirim request HTTPS via `URLSession`.
2. Server mengirimkan rantai sertifikat X.509 selama TLS handshake.
3. `URLSessionDelegate` mencegat event `didReceive challenge: URLAuthenticationChallenge`.
4. Delegate mengekstrak Leaf Certificate dari Server Trust object (`SecTrust`).
5. Ekstrak header `SubjectPublicKeyInfo` menggunakan Core Foundation ASN.1 APIs.
6. Hitung digest SHA-256 dari byte array SPKI.
7. Encode digest ke Base64, lalu bandingkan dengan hardcoded pin list (Primary Pin & Backup Pin).
8. Jika cocok, panggil `completionHandler(.useCredential, credential)`. Jika tidak cocok, batalkan koneksi secara fatal melalui `completionHandler(.cancelAuthenticationChallenge, nil)`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Brankas Bank Swiss (Secure Enclave)
Bayangkan aplikasi Anda adalah kantor cabang bank biasa (Application Processor), sedangkan Secure Enclave adalah sebuah brankas baja tahan ledak di ruang bawah tanah (SEP) yang memiliki juru tulis independen di dalamnya. 
Ketika dokumen transaksi perlu dicap stempel rahasia (Private Key), kantor cabang tidak boleh membawa stempel keluar. Kantor cabang menyelipkan dokumen lewat celah kecil (Mailbox). Juru tulis di dalam brankas meminta pemilik akun menempelkan retina ke sensor khusus brankas. Jika cocok, juru tulis menempelkan stempel, lalu menyerahkan kembali dokumen yang sudah tertera stempel ke kantor cabang. Dokumen stempel valid, tetapi tak seorang pun di kantor cabang pernah menyentuh stempel aslinya.

#### Diagram RASP Verification Loop
```
[ App Launch / Critical Action ]
               |
               v
   +-----------------------+
   |  RASP Guardian Check  |
   +-----------------------+
               |
    +----------+----------+--------------------+
    |                     |                    |
    v                     v                    v
[ Dyld Hook Check ]   [ Ptrace Check ]   [ Syscall Sandbox Check ]
    |                     |                    |
    | Frida / Substrate   | Debugger Attached  | Fork / Jailbreak File
    +----------+----------+--------------------+
               |
        Ada Anomali?
        /          \
     (Ya)          (Tidak)
      /              \
     v                v
[ Wipe Keys & ]  [ Lanjutkan Eksekusi ]
[ Fatal Exit  ]
```

---

### 7. Implementation: Simple & Practical Examples

Berikut adalah implementasi modular arsitektur keamanan enterprise berbasis Swift murni.

#### File 1: `SecureEnclaveManager.swift`
Mengelola pembuatan kunci asimetris NIST P-256 yang dilindungi secara hardware di dalam Secure Enclave dengan policy biometrik ketat.

```swift
import Foundation
import Security
import LocalAuthentication
import CryptoKit

public enum SecureEnclaveError: Error, LocalizedError {
    case secureEnclaveNotSupported
    case accessControlCreationFailed
    case keyGenerationFailed(CFError?)
    case keyNotFound
    case signingFailed(CFError?)
    case signatureVerificationFailed
    case biometryStateInvalidated

    public var errorDescription: String? {
        switch self {
        case .secureEnclaveNotSupported:
            return "Perangkat ini tidak memiliki Secure Enclave hardware."
        case .accessControlCreationFailed:
            return "Gagal menginisialisasi SecAccessControl."
        case .keyGenerationFailed(let cfError):
            return "Gagal membuat hardware-backed key: \(String(describing: cfError))"
        case .keyNotFound:
            return "Hardware-backed key tidak ditemukan dalam Secure Enclave."
        case .signingFailed(let cfError):
            return "Operasi signing di Secure Enclave gagal: \(String(describing: cfError))"
        case .signatureVerificationFailed:
            return "Verifikasi signature kriptografis gagal."
        case .biometryStateInvalidated:
            return "Kunci biometrik telah di-invalidasi karena perubahan database Face ID/Touch ID."
        }
    }
}

public final class SecureEnclaveManager: @unchecked Sendable {
    private let keyTag = "com.enterprise.banking.hardwareKey"
    
    public init() {}
    
    public func isSecureEnclaveAvailable() -> Bool {
        return SecureEnclave.isAvailable
    }
    
    public func generateHardwareProtectedKey() throws -> SecKey {
        guard isSecureEnclaveAvailable() else {
            throw SecureEnclaveError.secureEnclaveNotSupported
        }
        
        // Hapus kunci lama jika ada untuk idempotency
        deleteHardwareKey()
        
        var accessControlError: Unmanaged<CFError>?
        guard let accessControl = SecAccessControlCreateWithFlags(
            kCFAllocatorDefault,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            [.privateKeyUsage, .biometryCurrentSet],
            &accessControlError
        ) else {
            throw SecureEnclaveError.accessControlCreationFailed
        }
        
        let attributes: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String: 256,
            kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
            kSec