# BAB 06: DEFENSIVE SECURITY ENGINEERING
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengisolasi Kerentanan Runtime PHP**: Membedah mekanisme internal Zend Engine terkait *object deserialization*, *dynamic symbol resolution*, dan mitigasi eksploitasi memory corruption/gadget chain (POP Chains).
- **Membangun Pipeline Kriptografi Tingkat Lanjut**: Mengimplementasikan *Envelope Encryption* (KMS/HSM pattern) menggunakan Libsodium modern (`crypto_aead_xchacha20poly1305_ietf`) dengan dukungan *Key Rotation* dan *Blind Indexing* untuk pencarian data terenkripsi.
- **Merekayasa SSRF-Resistant Networking Engine**: Mengembangkan client HTTP lapis ganda dengan mitigasi *DNS Rebinding*, *IPv4/IPv6 dual-stack parsing*, serta *zero-trust IP pinning* menggunakan `CURLOPT_RESOLVE` dan custom stream contexts.
- **Merancang Arsitektur Zero-Trust File Ingestion**: Mengamankan pipeline pemrosesan berkas biner dari serangan *Polyglot execution*, *MIME-type spoofing*, dan *ImageTragick/Ghostscript exploits* melalui pembersihan metadata dan *sandboxed isolated re-encoding*.
- **Menerapkan Defense-in-Depth Runtime Configuration**: Mengonfigurasi lingkungan PHP 8.2+ berstandar enterprise (PCI-DSS 4.0 & ISO 27001) mencakup *CSP Nonce injection*, *sandboxed stream wrappers*, dan *strict process isolation*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Arsitektur Internal PHP 8.x**: Siklus hidup eksekusi PHP (MINIT, RINIT, RSHUTDOWN, MSHUTDOWN), Zval memory layout, dan manajemen memori Zend Engine.
- **Kriptografi Dasar**: Simetris vs Asimetris, Hashing (Argon2id, SHA-256), HMAC, dan prinsip *Initialization Vector* (IV) / *Nonce*.
- **Protokol Jaringan Lanjutan**: Model OSI, DNS resolution lifecycle, CIDR routing (RFC 1918, RFC 3927, RFC 4193), dan socket programming.
- **OWASP Top 10 (API & Web)**: Pemahaman konseptual mendalam terkait Insecure Deserialization, SSRF, IDOR, dan RCE.

---

### 3. Concept & Internal Architecture

#### 3.1 Zend Engine Serialization & The Anatomy of POP Chains

Mekanisme `serialize()` dan `unserialize()` pada PHP mentransformasikan representasi in-memory objek Zend (`zend_object`) menjadi format string terstruktur yang menyertakan relasi kelas, properti, dan visibilitasnya. 

```
[String Data] 
     │
     ▼
Zend Parser / Lexer ──► Tokenize class name & properties
     │
     ▼
Class Autoloading ──► Menemukan definisi kelas di memory
     │
     ▼
zend_object Allocation ──► Alokasi hash table properti
     │
     ▼
Lifecycle Triggers ──► __wakeup() / __destruct() / __toString()
```

Bahaya fundamental terjadi ketika `unserialize()` dipanggil pada data yang dikontrol pengguna:
1. **Instantiation Hazard**: PHP secara otomatis menginisialisasi objek dari kelas manapun yang ada dalam lingkup aplikasi (*autoloaded* via Composer).
2. **Gadget Execution**: Attacker tidak menyuntikkan kode eksekusi baru, melainkan merangkai potongan kode yang sah (*gadgets*) yang ada pada method `__destruct()`, `__wakeup()`, `__toString()`, atau `__call()`. Rangkaian ini disebut **Property-Oriented Programming (POP) Chain**.
3. **Internal Mitigation Engine**:
   PHP 7.0+ memperkenalkan opsi `allowed_classes`. Namun, pada arsitektur produksi modern, mitigasi tingkat lanjut mengharuskan migrasi penuh ke format serialisasi berbasis skema deklaratif (*MessagePack* atau *JSON Schema*) dengan parser terisolasi yang sama sekali tidak memicu siklus hidup objek PHP.

#### 3.2 DNS Resolution, Socket Streams, dan SSRF Internals

Server-Side Request Forgery (SSRF) tingkat lanjut mengeksploitasi celah waktu (*Time-of-Check to Time-of-Use* - TOCTOU) antara resolusi nama domain dan inisiasi handshake TCP.

```
Attacker DNS Server
    │
    ├─ (1) Lookup Check ──► Resolves to 1.1.1.1 (Valid Public IP)
    │                       Check Passes!
    │
    └─ (2) Socket Connect ─► Resolves to 169.254.169.254 (AWS Metadata)
                            Exploitation Occurs! (DNS Rebinding)
```

Fungsi standar PHP seperti `file_get_contents()` atau `curl_exec()` mendelegasikan DNS lookup ke resolver glibc (`getaddrinfo`). Celah ini rentan terhadap:
- **DNS Rebinding**: DNS server penyerang merespons dengan TTL (Time To Live) bernilai `0`. Panggilan validasi resolver pertama menghasilkan alamat publik, namun panggilan *socket connect* mikrodetik berikutnya menghasilkan loopback (`127.0.0.1`) atau alamat metadata (`169.254.169.254`).
- **Octal/Hex IPv4 Obfuscation**: String seperti `0177.0.0.1` atau `0x7f.0.0.1` diterjemahkan oleh socket stack C sebagai `127.0.0.1`, melewati regex validasi URL yang buruk.
- **Architectural Solution**: *Zero-Trust Resolution Pinning*. DNS di-resolve satu kali secara eksplisit di layer aplikasi, IP divalidasi terhadap *blacklist* CIDR privat/reserved, kemudian socket HTTP dipaksa terhubung ke IP tersebut menggunakan direktif low-level cURL (`CURLOPT_RESOLVE`), sehingga memutus ketergantungan pada lookup sekunder sistem operasi.

#### 3.3 Libsodium AEAD Architecture & Envelope Encryption

Penyimpanan data sensitif (PII, tokens, data finansial) memerlukan *Authenticated Encryption with Associated Data* (AEAD). Standar industri modern PHP menggunakan **XChaCha20-Poly1305-IETF** yang memiliki keunggulan atas AES-256-GCM:
- **Nonce Misuse Resistance**: XChaCha20 menggunakan nonce 192-bit (24 byte). Kemungkinan tabrakan nonce (*nonce reuse collision*) saat di-generate via `random_bytes()` secara acak adalah $1 \times 10^{-18}$, secara matematis meniadakan risiko catastrophic failure yang lazim terjadi pada AES-GCM (yang noncenya dibatasi 96-bit).
- **Associated Data Verification**: Mengizinkan metadata (seperti `user_id` atau `created_at`) diikat secara kriptografis ke ciphertext tanpa menyimpannya secara terenkripsi, memitigasi serangan *ciphertext swapping* antar baris database.

Pada skala enterprise, enkripsi tidak dilakukan dengan membebankan Kunci Utama (*Master Key*) langsung ke seluruh baris database. Digunakan pola **Envelope Encryption**:

```
[KMS / Vault / HSM]
        │
   (Generate DEK)
        │
        ├──► Data Encryption Key (DEK Plaintext) ──► Enkripsi Payload Lokal ──► [Encrypted Data]
        │                                                                              │
        └──► Encrypted DEK (Via KEK) ──────────────────────────────────────────────────┴──► [Database Row]
```

---

### 4. Why & What

| Dimensi Keamanan | Implementasi Tradisional / Rapuh | Arsitektur Enterprise Defensive |
| :--- | :--- | :--- |
| **Integrasi Kriptografi** | Menggunakan `openssl_encrypt('aes-256-cbc')` dengan shared static key pada file `.env`. Rentan *Padding Oracle Attack* dan *key leakage*. | **Envelope Encryption via Libsodium AEAD**. KEK (*Key Encryption Key*) diisolasi di HSM/KMS. DEK (*Data Encryption Key*) dibuat unik per-record. |
| **Network Egress (SSRF)** | Validasi via `filter_var($url, FILTER_VALIDATE_URL)` dan blacklist regex kata `localhost`. | **Custom Transport Handler**. Explicit DNS extraction, IP canonicalization, filter blok CIDR reserved/private, IP-pinning transport mapping via `CURLOPT_RESOLVE`. |
| **Penerimaan Berkas** | Mengecek ekstensi file dan `$_FILES['upload']['type']` (MIME tipe yang dikirim client via HTTP Header). | **Strict Binary Verification Pipeline**. Pengecekan magic byte, sanitasi metadata EXIF, sandboxed format trans-decoding menggunakan worker terisolasi. |
| **Deserialisasi Data** | Menggunakan `unserialize()` native untuk cache internal atau session storage. | **JSON Schema Driven Engine**. Larangan mutlak native deserialization. Implementasi safe deserializer menggunakan typed DTOs & strict schema contract. |

---

### 5. How (Workflow Detail)

#### Workflow Pipeline: Safe Ingestion & Secure Transport Layer

```
Input Request (Outgoing URL Request)
  │
  ├─► [1. URI Normalization] : Parse scheme (hanya HTTP/HTTPS diizinkan), host, & port
  │
  ├─► [2. Isolated DNS Resolve] : Panggil dns_get_record() untuk IPv4 & IPv6
  │
  ├─► [3. CIDR Validation Layer] : Cocokkan semua IP hasil resolve terhadap:
  │       - RFC 1918 (Private: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  │       - RFC 3927 / RFC 4291 (Link-Local / IPv6 loopback)
  │       - Cloud Metadata (169.254.169.254, metadata.google.internal)
  │       * Bila match salah satu -> Reject Execution (Throw SecurityException)
  │
  ├─► [4. Transport Pinning] :
  │       - Siapkan HTTP Client (cURL handler)
  │       - Inject mapping ke CURLOPT_RESOLVE: "host:port:validated_ip"
  │       - Nonaktifkan automatic redirect tracking (CURLOPT_FOLLOWLOCATION = false)
  │
  └─► [5. Safe Dispatch] : Eksekusi request ke IP target terisolasi
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengiriman Pos dengan Deteksi Bom & Valas

Bayangkan Anda mengoperasikan kantor pos pribadi untuk sebuah korporasi finansial:
1. **Insecure Workflow**: Kurir menerima bingkisan bertuliskan "Kado Natal" (MIME header dari client). Tanpa membuka, kurir langsung menaruhnya di meja direktur (Server Filesystem). Ketika dibuka, bingkisan tersebut ternyata berisi bahan peledak (Polyglot Web Shell).
2. **SSRF Mitigation**: Seorang karyawan menyuruh kurir: "Tolong ambilkan amplop di alamat: Menara B, Lantai 5" (Target URL). Kurir melihat buku peta resmi (Isolated DNS), memeriksa apakah alamat tersebut adalah brankas kantor internal sendiri (Private Subnet). Jika ya, kurir menolak berangkat. Setelah dipastikan aman, kurir mengunci koordinat GPS (IP Pinning), sehingga meskipun plang nama jalan diubah saat ia di perjalanan (DNS Rebinding), ia tetap menuju titik fisik awal yang aman.

```
       ZERO-TRUST NETWORKING (ANTI-SSRF ENGINE)
       =======================================
       
[User Input URL]
       │
       ▼
 [ URL Parser ] ──► (Scheme != http/https?) ──► [ ABORT: Protocol Illegal ]
       │
       ▼
 [ DNS Pinning ] ──► Resolve to IPs: [ 192.0.2.1, 169.254.169.254 ]
       │
       ├──► Check 192.0.2.1       ──► OK (Public IP)
       └──► Check 169.254.169.254 ──► [ ABORT: Reserved Cloud Metadata! ]
       │
       ▼ (Semua lolos pengecekan)
 [ cURL Pipeline ] 
       │
       ├── Socket forced via: CURLOPT_RESOLVE
       └── CURLOPT_FOLLOWLOCATION: DISABLED (Redirect dievaluasi ulang via engine yang sama)
       │
       ▼
 [ Remote Server ]
```

---

### 7. Code Implementation

#### 7.1 Simple Example: Constant-Time Token & Memory-Safe Comparisons

Menggunakan pembandingan string konvensional (`===`) mengekspos aplikasi pada **Timing Attacks** (peretas mengukur selisih nanodetik respons server untuk menebak karakter per karakter). Solusi defensif memanfaatkan primitive konstan dari Libsodium.

```php
<?php

declare(strict_types=1);

namespace Enterprise\Security\Primitives;

final readonly class ConstantTimeValidator
{
    /**
     * Memvalidasi token otentikasi dalam waktu konstan (O(1) respect to length).
     * Mencegah timing attack side-channel leaks.
     */
    public static function verifyToken(string $knownToken, string $userProvidedToken): bool
    {
        // Libsodium sodium_memcmp memvalidasi array biner dalam waktu konstan
        // Ukuran harus identik agar perbandingan byte tidak bocor melalui ukuran buffer
        $knownLength = strlen($knownToken);
        $userLength = strlen($userProvidedToken);

        // Pertahankan evaluasi kalkulasi konstan untuk panjang string
        $result = hash_equals($knownToken, $userProvidedToken);

        return $result && ($knownLength === $userLength);
    }
}
```

#### 7.2 Practical Example: Production-Grade SSRF-Resistant HTTP Client Engine

Implementasi client transport yang menerapkan pemisahan resolusi DNS, validasi rentang CIDR, dan DNS Pinning.

```php
<?php

declare(strict_types=1);

namespace Enterprise\Security\Transport;

use RuntimeException;
use InvalidArgumentException;
use CurlHandle;

final class SafeHttpClient
{
    /**
     * Daftar CIDR yang dilarang keras untuk dikunjungi (Private, Loopback, Link-Local, Cloud Metadata).
     */
    private const array BLOCKED_CIDRS = [
        '0.0.0.0/8',          // Current network (RFC 1122)
        '10.0.0.0/8',         // Private-use networks (RFC 1918)
        '100.64.0.0/10',      // Shared Address Space (RFC 6598)
        '127.0.0.0/8',        // Loopback (RFC 1122)
        '169.254.0.0/16',     // Link Local & Cloud Metadata (RFC 3927 / AWS / GCP)
        '172.16.0.0/12',      // Private-use networks (RFC 1918)
        '192.0.0.0/24',       // IETF Protocol Assignments (RFC 6890)
        '192.0.2.0/24',       // TEST-NET-1 (RFC 5737)
        '192.168.0.0/16',     // Private-use networks (RFC 1918)
        '198.18.0.0/15',      // Network Interconnect Device Benchmark (RFC 2544)
        '198.51.100.0/24',    // TEST-NET-2 (RFC 5737)
        '203.0.113.0/24',     // TEST-NET-3 (RFC 5737)
        '224.0.0.0/4',        // IP multicast (RFC 5771)
        '240.0.0.0/4',        // Reserved for future use (RFC 1112)
        '255.255.255.255/32', // Broadcast
        '::1/128',            // IPv6 Loopback
        'fc00::/7',           // IPv6 Unique Local Addresses (ULA)
        'fe80::/10',          // IPv6 Link-Local Addresses
    ];

    /**
     * Mengeksekusi permintaan HTTP GET yang kebal terhadap SSRF dan DNS Rebinding.
     *
     * @param string $url URL target
     * @param int $timeout Detik batas maksimal eksekusi
     * @return string Isi respons dari target
     * @throws InvalidArgumentException|RuntimeException
     */
    public function get(string $url, int $timeout = 5): string
    {
        $parts = parse_url($url);
        if ($parts === false || !isset($parts['scheme'], $parts['host'])) {
            throw new InvalidArgumentException("URL invalid.");
        }

        $scheme = strtolower($parts['scheme']);
        if (!in_array($scheme, ['http', 'https'], true)) {
            throw new InvalidArgumentException("Protokol tidak diizinkan: {$scheme}");
        }

        $host = $parts['host'];
        $port = $parts['port'] ?? ($scheme === 'https' ? 443 : 80);

        // 1. Eksekusi Explicit DNS Resolution (A dan AAAA Record)
        $ipAddresses = $this->resolveDomainIps($host);

        if (empty($ipAddresses)) {
            throw new RuntimeException("Gagal me-resolve host atau host tidak memiliki IP: {$host}");
        }

        // 2. Validasi seluruh IP yang di-resolve terhadap Blocklist CIDR
        foreach ($ipAddresses as $ip) {
            if ($this->isIpBlocked($ip)) {
                throw new RuntimeException("Akses ditolak: IP {$ip} termasuk dalam blok restricted/private.");
            }
        }

        // 3. DNS Pinning: Gunakan IP publik pertama yang tervalidasi
        $targetIp = $ipAddresses[0];

        // 4. Inisialisasi Transport Terisolasi via cURL
        return $this->executeCurl($url, $host, $port, $targetIp, $timeout);
    }

    /**
     * Resolve host ke daftar representasi string IP (IPv4 & IPv6).
     * @return array<string>
     */
    private function resolveDomainIps(string $host): array
    {
        // Jika host sudah berupa representasi literal IP
        if (filter_var($host, FILTER_VALIDATE_IP)) {
            return [$host];
        }

        $ips = [];
        $dnsRecords = dns_get_record($host, DNS_A + DNS_AAAA);

        if ($dnsRecords === false) {
            return [];
        }

        foreach ($dnsRecords as $record) {
            if (isset($record['ip'])) {
                $ips[] = $record['ip'];
            } elseif (isset($record['ipv6'])) {
                $ips[] = $record['ipv6'];
            }
        }

        return array_values(array_unique($ips));
    }

    /**
     * Memeriksa apakah IP berada dalam rentang CIDR yang dilarang.
     */
    private function isIpBlocked(string $ip): bool
    {
        $ipBin = inet_pton($ip);
        if ($ipBin === false) {
            return true; // Malformed IP dianggap berbahaya
        }

        $isIpv4 = strlen($ipBin) === 4;

        foreach (self::BLOCKED_CIDRS as $cidr) {
            [$subnet, $mask] = explode('/', $cidr);
            $subnetBin = inet_pton($subnet);

            if ($subnetBin === false) {
                continue;
            }

            // Skip jika membandingkan keluarga IP yang berbeda
            if ((strlen($subnetBin) === 4) !== $isIpv4) {
                continue;
            }

            $maskInt = (int)$mask;
            if ($this->cidrMatch($ipBin, $subnetBin, $maskInt)) {
                return true;
            }
        }

        return false;
    }

    /**
     * Bitwise matching untuk subnet matching tanpa ketergantungan ekstensi eksternal.
     */
    private function cidrMatch(string $ipBin, string $subnetBin, int $mask): bool
    {
        $bytes = (int)($mask / 8);
        $bits = $mask % 8;

        // Bandingkan byte penuh
        if ($bytes > 0 && substr($ipBin, 0, $bytes) !== substr($subnetBin, 0, $bytes)) {
            return false;
        }

        // Bandingkan sisa bits
        if ($bits > 0) {
            $ipByte = ord($ipBin[$bytes]);
            $subnetByte = ord($subnetBin[$bytes]);
            $bitmask = (0xFF << (8 - $bits)) & 0xFF;

            if (($ipByte & $bitmask) !== ($subnetByte & $bitmask)) {
                return false;
            }
        }

        return true;
    }

    /**
     * Eksekusi koneksi low-level cURL dengan hardcoded routing table.
     */
    private function executeCurl(string $url, string $host, int $port, string $pinnedIp, int $timeout): string
    {
        $ch = curl_init();

        // Parameter CURLOPT_RESOLVE format: "HOST:PORT:ADDRESS"
        $resolveMap = ["{$host}:{$port}:{$pinnedIp}"];

        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => $timeout,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_RESOLVE => $resolveMap,
            // Matikan redirect otomatis untuk mencegah redirect-based SSRF ke endpoint lokal
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_MAXREDIRS => 0,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_PROTOCOLS => CURLPROTO_HTTP | CURLPROTO_HTTPS,
        ]);

        $response = curl_exec($ch);
        $error = curl_error($ch);
        $statusCode = curl_getinfo($ch, CURLINFO_RESPONSE_CODE);

        curl_close($ch);

        if ($response === false) {
            throw new RuntimeException("cURL Execution Failure: {$error}");
        }

        if ($statusCode >= 300 && $statusCode < 400) {
            throw new RuntimeException("Redirect terdeteksi. Redirect otomatis dinonaktifkan untuk mencegah bypass SSRF.");
        }

        return (string)$response;
    }
}
```

#### 7.3 Practical Example: Envelope Encryption Engine dengan Libsodium

Arsitektur enkripsi data terstruktur untuk entitas database menggunakan KEK (KMS Mocked) dan DEK unik yang dienkripsi per-payload.

```php
<?php

declare(strict_types=1);

namespace Enterprise\Security\Cryptography;

use SensitiveParameter;
use RuntimeException;

final readonly class EnvelopeEncryptionEngine
{
    /**
     * @param string $keyEncryptionKey KEK Master Key dari HSM/KMS (panjang wajib 32-byte)
     */
    public function __construct(
        #[\SensitiveParameter]
        private string $keyEncryptionKey
    ) {
        if (strlen($this->keyEncryptionKey) !== SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_KEYBYTES) {
            throw new RuntimeException("Invalid KEK length. Expected 32-byte binary key.");
        }
    }

    /**
     * Melakukan enkripsi data dengan pola envelope.
     *
     * @return array{ciphertext: string, encrypted_dek: string, iv: string, tag: string}
     */
    public function encrypt(
        #[\SensitiveParameter] string $plaintext,
        string $associatedData = ''
    ): array {
        // 1. Generate Data Encryption Key (DEK) acak sekali pakai
        $dek = sodium_crypto_aead_xchacha20poly1305_ietf_keygen();

        // 2. Buat Nonce untuk enkripsi Payload (24-byte untuk XChaCha20)
        $noncePayload = random_bytes(SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_NPUBBYTES);

        // 3. Enkripsi Payload menggunakan DEK
        $ciphertextWithTag = sodium_crypto_aead_xchacha20poly1305_ietf_encrypt(
            $plaintext,
            $associatedData,
            $noncePayload,
            $dek
        );

        // 4. Enkripsi DEK menggunakan KEK (Envelope Lock)
        $nonceDek = random_bytes(SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_NPUBBYTES);
        $encryptedDek = sodium_crypto_aead_xchacha20poly1305_ietf_encrypt(
            $dek,
            $associatedData,
            $nonceDek,
            $this->keyEncryptionKey
        );

        // 5. Bersihkan DEK dari memory space PHP runtime
        sodium_memzero($dek);

        return [
            'ciphertext' => base64_encode($ciphertextWithTag),
            'encrypted_dek' => base64_encode($nonceDek . $encryptedDek),
            'nonce' => base64_encode($noncePayload),
        ];
    }

    /**
     * Melakukan dekripsi envelope payload.
     */
    public function decrypt(
        string $base64Ciphertext,
        string $base64EncryptedDekPayload,
        string $base64Nonce,
        string $associatedData = ''
    ): string {
        $ciphertext = base64_decode($base64Ciphertext, true);
        $encryptedDekPayload = base64_decode($base64EncryptedDekPayload, true);
        $noncePayload = base64_decode($base64Nonce, true);

        if ($ciphertext === false || $encryptedDekPayload === false || $noncePayload === false) {
            throw new RuntimeException("Gagal melakukan decode Base64 payload kriptografi.");
        }

        // Ekstraksi Nonce KEK dan Ciphertext DEK
        $nonceLength = SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_NPUBBYTES;
        if (strlen($encryptedDekPayload) <= $nonceLength) {
            throw new RuntimeException("Ukuran payload DEK terenkripsi korup.");
        }

        $nonceDek = substr($encryptedDekPayload, 0, $nonceLength);
        $encryptedDek = substr($encryptedDekPayload, $nonceLength);

        // 1. Dekripsi DEK menggunakan KEK
        $dek = sodium_crypto_aead_xchacha20poly1305_ietf_decrypt(
            $encryptedDek,
            $associatedData,
            $nonceDek,
            $this->keyEncryptionKey
        );

        if ($dek === false) {
            throw new RuntimeException("Autentikasi KEK gagal: KEK salah atau data termanipulasi.");
        }

        // 2. Dekripsi Payload menggunakan DEK yang telah pulih
        $plaintext = sodium_crypto_aead_xchacha20poly1305_ietf_decrypt(
            $ciphertext,
            $associatedData,
            $noncePayload,
            $dek
        );

        // 3. Sanitasi DEK seketika setelah digunakan
        sodium_memzero($dek);

        if ($plaintext === false) {
            throw new RuntimeException("Autentikasi Payload gagal: Ciphertext atau Associated Data termanipulasi.");
        }

        return $plaintext;
    }
}
```

---

### 8. Real World Case Study: Financial Webhook Gateway Exploitation & Mitigation

#### Konteks Masalah
Sebuah platform Payment Gateway berbasis PHP 8.2 memproses webhook konfirmasi pembayaran dari ribuan merchant B2B. Fitur "Merchant Callback Verification" memvalidasi endpoint URL merchant dengan melakukan HTTP GET ping, lalu mengirimkan payload pembayaran via HTTP POST.

#### Insiden Keamanan (Root Cause Analysis)
1. **SSRF to AWS IMDSv1**: Penyerang mendaftarkan URL callback `http://169.254.169.254/latest/meta-data/iam/security-credentials/production-role`. Aplikasi hanya memvalidasi string dengan regex `!preg_match('/localhost|127\.0\.0\.1/', $url)`.
2. **Kompilasi Exploit**: Attacker mengekstrak token IAM AWS milik container ECS PHP, membajak bucket S3 penyimpanan data transaksi, dan memicu kebocoran 4.2 juta data rekening pelanggan.
3. **Double Whammy (POP Chain)**: Penyerang memanfaatkan header HTTP yang di-cache menggunakan serialisasi objek native (`unserialize()`) pada Redis cache cluster backend, memicu execution chain dari pustaka Monolog internal hingga mencapai *Remote Code Execution* (RCE).

#### Arsitektur Transformasi Defensif
1. **Network Egress Isolation**: Seluruh worker PHP pemroses webhook dipindahkan ke Private Isolated Subnet tanpa rute internet gateway langsung, melainkan diarahkan melalui Squid Proxy dengan policy ketat (Whitelisted FQDNs).
2. **Implementasi Safe Transport**: Pemasangan kelas `SafeHttpClient` (seperti pada Seksi 7.2) yang memblokir lookup ke 169.254.x.x, menerapkan DNS Pinning (`CURLOPT_RESOLVE`), dan menolak HTTP redirection (anti-TOCTOU).
3. **Deprecate Unserialize**: Format redis cache dimigrasikan dari `serialize()` PHP ke format biner protokoler aman via MessagePack (`msgpack_pack()` dan `msgpack_unpack()`), meniadakan kemampuan attacker mengeksekusi PHP Object Lifecycle.

---

### 9. Trade-offs

| Pendekatan / Algoritma | Keuntungan Keamanan | Dampak Latensi / CPU | Kompleksitas Skalabilitas | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **DNS-Pinning Manual via cURL** | Menutup 100% eksploitasi DNS Rebinding & TOCTOU race conditions. | +5ms - 15ms per outgoing call (overhead eksplisit DNS lookup via UDP/DoH). | Perlu mengelola dual-stack resolution IPv4 & IPv6 secara manual di level aplikasi. | Wajib untuk fitur Webhook, URL unfurling, dan dynamic integration proxy. |
| **Envelope Encryption (DEK/KEK)** | Kompromi 1 baris DB tidak merusak seluruh database; rotasi kunci KEK dapat dilakukan tanpa re-encrypt miliaran baris DB. | +2x kalkulasi AEAD per transaksi (enkripsi data + enkripsi kunci DEK). | Memerlukan integrasi eksternal KMS (HashiCorp Vault, AWS KMS) dan latency management cache DEK. | Wajib untuk atribut PII finansial (No Kartu Kredit, NIK, Rekening Bank). |
| **Argon2id (m=64MB, t=4, p=1)** | Kebal terhadap GPU/ASIC password cracking attacks. | ~250ms per hashing run; konsumsi memory PHP thread melonjak 64MB per auth call. | Batas throughput concurrent auth berkurang drastis; rentan Resource Exhaustion DoS jika diserang serentak. | Wajib untuk autentikasi user/admin; batas rate limit harus dipasang di Edge/Reverse Proxy. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kerentanan Parser URL: Ketidaksesuaian `parse_url()` vs RFC 3986
*Gejala*: Penyerang menggunakan format URI aneh seperti `http://user#@evil.com:80@legitimate.com` untuk mengelabui validasi.
```php
// SALAH: Mengandalkan parse_url() tanpa normalisasi host
$host = parse_url($url, PHP_URL_HOST);
if ($host === 'legitimate.com') { // Terlewati karena libcurl memproses '@' secara berbeda!
    curl_exec(curl_init($url));
}
```
*Mitigasi*: Parse URI menggunakan RFC 3986 compliant parser (misal: `League\Uri`) dan hanya passing alamat host/path yang telah dikonstruksi ulang secara bersih ke layer socket.

#### 2. False Sense of Security pada `$_FILES['type']`
*Gejala*: Mengizinkan berkas berbahaya masuk karena MIME type HTTP header dikendalikan attacker.
```php
// FATAL: Nilai ini dikirim oleh attacker via HTTP header "Content-Type"
if ($_FILES['document']['type'] !== 'application/pdf') {
    throw new SecurityException("Hanya menerima PDF!");
}
```
*Solusi Defensif*:
```php
// BENAR: Deteksi byte fisik asli berkas via libmagic di Zend Core
$finfo = new finfo(FILEINFO_MIME_TYPE);
$mimeType = $finfo->file($_FILES['document']['tmp_name']);
if ($mimeType !== 'application/pdf') {
    throw new SecurityException("Pelanggaran tipe berkas: MIME tidak valid.");
}
```

#### 3. Bocornya Nonce Reuse pada Stream Cipher
*Peringatan*: Jika menggunakan `sodium_crypto_aead_xchacha20poly1305_ietf_encrypt`, jangan pernah menyimpan nonce secara statis di file konfigurasi. Nonce **harus** di-generate via `random_bytes(24)` untuk setiap panggilan enkripsi individual, dan disimpan berdampingan dengan ciphertext.

---

### 11. Best Practices (Production Checklist)

#### Hardened `php.ini` Directive Checklist
- [ ] `allow_url_fopen = Off`: Menolak loading script jarak jauh melalui wrapper standard stream.
- [ ] `allow_url_include = Off`: Menutup exploit Remote File Inclusion (RFI) permanen.
- [ ] `expose_php = Off`: Menghilangkan fingerprint header `X-Powered-By`.
- [ ] `disable_functions = exec,passthru,shell_exec,system,proc_open,popen,curl_multi_exec,parse_ini_file,show_source`: Nonaktifkan eksekusi command shell sistemik.
- [ ] `open_basedir = /var/www/html:/tmp`: Membatasi filesystem traversal strictly pada working directory aplikasi dan temporary upload path.
- [ ] `session.cookie_httponly = 1`: Mencegah pembajakan token session via Client-side XSS.
- [ ] `session.cookie_secure = 1`: Memaksa transport token session hanya melalui layer TLS/HTTPS.
- [ ] `session.cookie_samesite = "Strict"`: Memitigasi ancaman CSRF (Cross-Site Request Forgery) dari baseline browser.

#### Content Security Policy (CSP) Nonce Generator Middleware
Injeksi CSP Nonce acak per-request menggunakan runtime generator kriptografis:

```php
<?php

declare(strict_types=1);

namespace Enterprise\Security\Http;

final class SecurityHeadersMiddleware
{
    public function handle(): void
    {
        // Generate cryptographic random nonce (16 bytes = 128 bit)
        $nonce = base64_encode(random_bytes(16));

        // Daftarkan ke register global / dependency container agar bisa diakses template engine
        $GLOBALS['CSP_NONCE'] = $nonce;

        $cspHeader = "default-src 'self'; " .
                     "script-src 'self' 'nonce-{$nonce}' 'strict-dynamic'; " .
                     "object-src 'none'; " .
                     "base-uri 'none'; " .
                     "require-trusted-types-for 'script';";

        header("Content-Security-Policy: {$cspHeader}");
        header("X-Content-Type-Options: nosniff");
        header("X-Frame-Options: DENY");
        header("Referrer-Policy: strict-origin-when-cross-origin");
    }
}
```

---

### 12. Hands-on Practice

Buat dan simpan struktur proyek berikut di direktori: `hands-on/m02/`

```
hands-on/m02/
├── composer.json
├── docker-compose.yml
├── Dockerfile
├── src/
│   ├── Storage/
│   │   └── SecureFileReceiver.php
│   └── Network/
│       └── SSRFShield.php
└── test_harness.php
```

#### Langkah 1: Inisialisasi Lingkungan & Dependencies
Simpan pada `hands-on/m02/composer.json`:
```json
{
    "name": "enterprise/defensive-sec-m02",
    "type": "project",
    "require": {
        "php": ">=8.2"
    },
    "autoload": {
        "psr-4": {
            "Enterprise\\Security\\": "src/"
        }
    }
}
```

#### Langkah 2: Buat Pipeline Upload Sanitizer
Simpan pada `hands-on/m02/src/Storage/SecureFileReceiver.php`:
Implementasikan sanitasi upload biner dari serangan SVG XSS, Polyglot, dan MIME spoofing:

```php
<?php

declare(strict_types=1);

namespace Enterprise\Security\Storage;

use RuntimeException;
use finfo;

final class SecureFileReceiver
{
    private const array ALLOWED_MIME_MAP = [
        'image/jpeg' => 'jpg',
        'image/png'  => 'png',
        'application/pdf' => 'pdf',
    ];

    /**
     * Memproses berkas yang diunggah secara aman.
     * 
     * @param array{tmp_name: string, name: string, size: int, error: int} $fileArray Elemen dari $_FILES
     * @param string $destinationDir Direktori target absolut
     * @return string Path berkas yang telah disimpan dengan ekstensi canonical
     */
    public function ingest(array $fileArray, string $destinationDir): string
    {
        if ($fileArray['error'] !== UPLOAD_ERR_OK) {
            throw new RuntimeException("Upload gagal dengan error code: {$fileArray['error']}");
        }

        $tmpPath = $fileArray['tmp_name'];

        if (!is_uploaded_file($tmpPath)) {
            throw new RuntimeException("Potensi path traversal: berkas bukan upload sah.");
        }

        // 1. Validasi Ukuran (Max 2MB)
        if ($fileArray['size'] > 2 * 1024 * 1024) {
            throw new RuntimeException("Ukuran berkas melebihi batas 2MB.");
        }

        // 2. Strict MIME Type Validation via Magic Bytes
        $finfo = new finfo(FILEINFO_MIME_TYPE);
        $detectedMime = $finfo->file($tmpPath);

        if (!isset(self::ALLOWED_MIME_MAP[$detectedMime])) {
            throw new RuntimeException("MIME type tidak diizinkan: {$detectedMime}");
        }

        $extension = self::ALLOWED_MIME_MAP[$detectedMime];

        // 3. Sanitasi Konten Gambar (Strip Metadata / Exif / Payload Shell)
        if (in_array($detectedMime, ['image/jpeg', 'image/png'], true)) {
            $this->neutralizeImage($tmpPath, $detectedMime);
        }

        // 4. Generate Nama Acak Unik (Cegah Overwriting & File Path Guessing)
        $newFileName = bin2hex(random_bytes(16)) . '.' . $extension;
        $targetFullPath = rtrim($destinationDir, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . $newFileName;

        if (!move_uploaded_file($tmpPath, $targetFullPath)) {
            throw new RuntimeException("Gagal memindahkan berkas yang telah tervalidasi.");
        }

        return $targetFullPath;
    }

    /**
     * Rekonstruksi ulang gambar secara penuh untuk membakar/menghilangkan injection payload pada EXIF.
     */
    private function neutralizeImage(string $filePath, string $mime): void
    {
        if ($mime === 'image/jpeg') {
            $imageResource = @imagecreatefromjpeg($filePath);
            if ($imageResource === false) {
                throw new RuntimeException("Berkas gambar JPEG korup atau mengandung payload invalid.");
            }
            imagejpeg($imageResource, $filePath, 85);
            imagedestroy($imageResource);
        } elseif ($mime === 'image/png') {
            $imageResource = @imagecreatefrompng($filePath);
            if ($imageResource === false) {
                throw new RuntimeException("Berkas gambar PNG korup atau mengandung payload invalid.");
            }
            imagepng($imageResource, $filePath, 8);
            imagedestroy($imageResource);
        }
    }
}
```

#### Langkah 3: Eksekusi Test Harness
Simpan pada `hands-on/m02/test_harness.php`:
```php
<?php

declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

use Enterprise\Security\Transport\SafeHttpClient;
use Enterprise\Security\Cryptography\EnvelopeEncryptionEngine;

echo "=== MEMULAI TEST DEFENSIVE ARCHITECTURE ===\n";

// TEST 1: Enkripsi Envelope
$kek = random_bytes(32);
$engine = new EnvelopeEncryptionEngine($kek);

$sensitivePii = "31710123456780001"; // NIK Nasabah
$encrypted = $engine->encrypt($sensitivePii, 'USER_CONTEXT_ID_999');
$decrypted = $engine->decrypt(
    $encrypted['ciphertext'],
    $encrypted['encrypted_dek'],
    $encrypted['nonce'],
    'USER_CONTEXT_ID_999'
);

assert($sensitivePii === $decrypted, "Decryption payload tidak cocok!");
echo "[✓] Test 1: Envelope Encryption & Decryption Sukses.\n";

// TEST 2: Anti-SSRF Blocking Test
$client = new SafeHttpClient();
try {
    // Coba tembak localhost IP literal
    $client->get('http://127.0.0.1:8080/metrics');
    echo "[X] Test 2 Gagal: Localhost tidak terblokir!\n";
} catch (RuntimeException $e) {
    echo "[✓] Test 2: Blokir Akses SSRF Loopback Berhasil: " . $e->getMessage() . "\n";
}

try {
    // Coba tembak Cloud Metadata AWS
    $client->get('http://169.254.169.254/latest/meta-data/');
    echo "[X] Test 2 Gagal: AWS Metadata tidak terblokir!\n";
} catch (RuntimeException $e) {
    echo "[✓] Test 2: Blokir Akses SSRF Cloud Metadata Berhasil: " . $e->getMessage() . "\n";
}

echo "=== SELURUH VERIFIKASI SELESAI DENGAN SUKSES ===\n";
```

Jalankan pengujian via command-line:
```bash
composer dump-autoload
php test_harness.php
```

---

### 13. Exercise

#### Level Easy
Buat sebuah kelas `SessionTokenEngine` yang membuat token sesi cryptographically secure 256-bit dan menghasilkan string representasi Base64URL (bukan Base64 standar, aman untuk URL tanpa encoding `%2B` dsb). Implementasikan method verifikasi string menggunakan constant-time matching.

#### Level Medium
Kembangkan custom stream wrapper bernama `SecureReadOnlyStream` (mewarisi implementasi stream wrapper internal PHP) yang:
- Mencegah mode penulisan (`w`, `a`, `x`).
- Membatasi pembacaan berkas hanya pada direktori `/var/data/exports/`.
- Mencegah path traversal dengan resolving symlinks menggunakan `realpath()` sebelum mengizinkan handle stream terbuka via `stream_open`.

#### Level Hard
Rancang komponen **Blind Index Search Engine** berbasis hash HMAC-SHA256 untuk database PII. Data kolom (misal: Email) dienkripsi secara penuh dengan Libsodium (tidak bisa dicari dengan query `LIKE`), namun pencarian eksak (`WHERE blind_index = :hash`) tetap dapat dilakukan secara aman tanpa membocorkan plaintext atau memicu Dictionary Attack. Sertakan salt dinamis yang di-derive menggunakan HKDF (*HMAC-based Key Derivation Function*).

---

### 14. Challenge

**Skenario**: Anda ditunjuk sebagai Chief Security Architect untuk sistem Core Banking yang harus mematuhi PCI-DSS 4.0. Sistem menerima request pemrosesan pembayaran dari ribuan merchant melalui format JSON terkompresi GZIP.
- **Vulnerability Surface**: Serangan *Zip Bomb* (DoS memori via uncompressing 10MB file menjadi 50GB di RAM), ancaman *JSON Insecure Object Deserialization*, dan transmisi data kartu kredit mentah di log sistem.
- **Tugas Arsitektural**:
  1. Rancang pipeline `SecurePayloadIngestor` yang melakukan verifikasi ukuran payload terkompresi secara *streaming* (baca byte per byte; batalkan eksekusi jika rasio dekompresi melebihi 1:10 atau ukuran total dekompresi melebihi 20MB secara real-time tanpa mengonsumsi RAM).
  2. Implementasikan *JSON Schema Validator Parser* manual/custom yang mem-parsing tipe data numerik dan string ke Immutable Value Objects tanpa menyentuh method reflection dinamis PHP.
  3. Buat custom log filter layer untuk Monolog yang mendeteksi nomor kartu kredit (Luhn Algorithm pattern recognition) pada string apapun dan melakukan masking otomatis (`4111-XXXX-XXXX-1111`) sebelum string log mencapai disk/output stream.
- **Batasan**: Larangan mutlak menggunakan `exec()`, dependensi library luar non-PSR, atau fungsi `unserialize()`.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Mengapa fungsi `hash_equals()` atau `sodium_memcmp()` wajib digunakan untuk membandingkan password hash/token, alih-alih operator kesetaraan standar `===`?
2. Apa fungsi parameter `#[\SensitiveParameter]` yang diperkenalkan pada PHP 8.2 dari kacamata rekayasa keamanan defensif?
3. Mengapa konfigurasi `allow_url_include = Off` pada `php.ini` bersifat kritikal pada server produksi?
4. Manakah ekstensi PHP modern yang direkomendasikan secara resmi oleh core team PHP untuk primitive kriptografi simetris dan hashing kata sandi tingkat lanjut: Mcrypt, OpenSSL, atau Libsodium?
5. Mengapa mengecek `$_FILES['input_name']['type']` tidak memberikan jaminan keamanan apapun terhadap validitas tipe file yang diunggah?

#### Bagian 2: Intermediate (5 Pertanyaan)
1. Jelaskan mekanisme terjadinya serangan **DNS Rebinding** pada aplikasi web dan mengapa pengecekan domain via `filter_var($url, FILTER_VALIDATE_URL)` tidak mampu mencegah serangan ini!
2. Dalam implementasi algoritma XChaCha20-Poly1305 AEAD, apa yang terjadi pada integritas data jika *Associated Data* (AD) yang dipasok saat proses dekripsi berbeda 1 byte dari AD saat enkripsi?
3. Apa kelemahan utama fungsi deserialisasi native PHP (`unserialize`) dibanding pendekatan *data contract schema* berbasis JSON Schema?
4. Bagaimana mekanisme flag `open_basedir` pada Zend Engine mengisolasi eksekusi I/O filesystem aplikasi?
5. Sebutkan risiko keamanan jika direktif cURL `CURLOPT_FOLLOWLOCATION` diaktifkan secara default pada HTTP client yang bertugas memproses webhook pihak ketiga!

#### Bagian 3: Production Scenarios (3 Kasus)
1. **Skenario Kasus A**: Tim Anda menemukan spike memori masif pada klaster worker PHP saat memproses berkas gambar PNG dari pengguna. File tersebut berukuran hanya 50KB di disk, namun membuat worker crash karena OOM (*Out of Memory*). Jelaskan teknik eksploitasi apa yang digunakan attacker dan bagaimana mitigasi defensifnya di level kode PHP!
2. **Skenario Kasus B**: Sebuah microservice internal memvalidasi outgoing URL dengan memanggil `gethostbyname($domain)`. Jika IP bukan blok private, maka service memanggil `file_get_contents($url)`. Identifikasi celah fatal dari arsitektur ini dan susun langkah remediasinya!
3. **Skenario Kasus C**: Pada database produksi, Anda mendapati bahwa dua baris data pengguna yang berbeda memiliki nilai *Encrypted Password Hash* yang identik karena enkripsi CBC tanpa IV unik. Mengapa situasi ini melanggar kepatuhan regulasi keamanan enterprise dan bagaimana desain arsitektur enkripsi yang benar untuk memperbaikinya?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1
1. Operator `===` melakukan *early-exit* (berhenti pada byte pertama yang berbeda), menyebabkan waktu eksekusi bervariasi bergantung pada kecocokan karakter (Timing Side-Channel Attack). `hash_equals` mengeksekusi iterasi seluruh panjang byte secara konstan (O(1)).
2. Mencegah nilai variabel sensitif (password, secret key, PII) bocor ke stack traces, log error, atau APM reporting tools saat terjadi fatal error/exception.
3. Menutup celah eksploitasi Remote File Inclusion (RFI) di mana penyerang memaksa fungsi seperti `include` atau `require` mengeksekusi payload PHP jarak jauh dari URL eksternal.
4. Libsodium. (Mcrypt sudah deprecated dan dihapus; OpenSSL memiliki API rawan salah konfigurasi dan rentan memory bug implementasi C).
5. Nilai tersebut diekstrak dari header HTTP `Content-Type` yang dikirimkan oleh browser client, yang dapat dimanipulasi secara trivial menggunakan proxy seperti Burp Suite atau cURL.

#### Bagian 2
1. Penyerang mengontrol otoritatif nameserver domain dengan TTL 0. Lookup pertama menghasilkan IP publik (melewati filter validasi), namun saat socket HTTP aplikasi melakukan resolve kedua untuk connect, IP dialihkan ke loopback/metadata private (`127.0.0.1` atau `169.254.169.254`).
2. Proses dekripsi akan gagal total dan melempar exception/false. Tag Polyglot AEAD memvalidasi integritas ciphertext sekaligus integritas associated data. Jika AD tidak identik, data dianggap mengalami tampering (pemalsuan).
3. `unserialize()` secara otomatis memicu eksekusi *magic methods* (`__wakeup`, `__destruct`, `__toString`) pada objek yang didefinisikan dalam memori aplikasi, memungkinkan terbentuknya POP Gadget Chains untuk RCE. JSON Schema parser hanya membentuk data array/primitive murni tanpa siklus hidup eksekusi objek runtime.
4. Membatasi pemanggilan API POSIX filesystem libc dari level C Zend Engine. Setiap fungsi filesystem PHP mencocokkan canonical path target dengan prefiks path yang diizinkan pada string `open_basedir`. Jika di luar jangkauan, PHP menghentikan eksekusi sebelum syscall diteruskan ke kernel OS.
5. Jika target server merespons dengan HTTP redirect (301/302) ke alamat internal (contoh: `Location: http://169.254.169.254/latest/meta-data/`), cURL engine akan secara otomatis mengejar target baru tersebut dan mengeksekusi SSRF, melewati filter validasi URL lapis pertama.

#### Bagian 3
1. **Pixel Flood Attack (Decompression Bomb)**. File PNG berukuran kecil di disk dikompresi sedemikian rupa, namun memiliki header lebar dan tinggi raksasa (misal: 100,000 x 100,000 pixel). Saat fungsi seperti `imagecreatefrompng()` dipanggil, Zend Engine mengalokasikan RAM fisik untuk canvas mentah bitmap (RGBA 4 byte per pixel = ~40 GB RAM), memicu crash OOM. **Mitigasi**: Panggil `getimagesize()` terlebih dahulu; validasi bahwa `width * height * bpp` tidak melampaui batas ambang alokasi RAM yang aman (misal: maks 4000x4000 pixel) sebelum melakukan decoding biner.
2. Celah fatal: **TOCTOU Race Condition (DNS Rebinding)**. Domain di-resolve pada `gethostbyname()`, namun di-resolve ulang oleh libc resolver saat `file_get_contents()` dipanggil. Attacker merespons dengan IP berbeda pada resolve kedua. Selain itu, `file_get_contents` secara default mengejar redirect. **Remediasi**: Migrasi ke custom cURL transport dengan `CURLOPT_RESOLVE` terisolasi, nonaktifkan redirect, dan gunakan satu kali resolusi IP untuk validasi dan koneksi socket.
3. Pelanggaran: Ketiadaan *Ciphertext Indistinguishability* (Semantic Security). Jika data yang sama selalu menghasilkan ciphertext yang sama, penyerang dapat melakukan korelasi data (*inference attack* / *frequency analysis*). **Remediasi**: Terapkan algoritma AEAD (XChaCha20-Poly1305) dengan Nonce acak 24-byte unik per baris data, dipadukan dengan pola Envelope Encryption (KEK/DEK) dan Blind Indexing untuk kebutuhan query.

---

### 16. Summary

- **Fondasi Defensif Runtime**: Keamanan aplikasi PHP berakar dari konfigurasi runtime yang ketat (`php.ini`, open_basedir, mitigasi POP Chain dengan meniadakan native `unserialize`).
- **Kriptografi Modern**: Tinggalkan implementasi cipher lama. Standar arsitektur industri enterprise berpusat pada penggunaan Libsodium AEAD (XChaCha20-Poly1305), Envelope Encryption (KEK/DEK separation), dan constant-time execution (`hash_equals`).
- **Zero-Trust Network Operations**: Mitigasi SSRF dan DNS Rebinding menuntut pemutusan ketergantungan pada generic resolver OS melalui isolasi DNS resolution, strict CIDR filtering, dan low-level transport socket pinning via `CURLOPT_RESOLVE`.
- **Integrasi Input & Berkas Biner**: Validasi berkas harus dilakukan berbasis deteksi magic bytes internal OS, mitigasi decompression bomb sebelum buffer parsing, dan pelepasan/re-encoding metadata biner secara total sebelum data diizinkan menetap di filesystem storage enterprise.