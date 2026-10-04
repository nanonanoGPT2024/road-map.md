# Bab 06 Module 01: Defensive Security Engineering

---

## SEKSI 01 — IDENTITAS MODUL

*   **Track:** Backend Engineering & Software Architecture
*   **Course:** 02-Programming-Languages
*   **Module:** Bab 06 Module 01 — Defensive Security Engineering
*   **Level:** Advanced (L4/L5)
*   **Prerequisites:**
    *   Pemahaman mendalam tentang siklus hidup request-response PHP (SAPI, FastCGI/PHP-FPM).
    *   Penguasaan PHP 8.2+ (Strict Types, Attributes, Readonly Classes/Properties).
    *   Arsitektur MVC/Clean Architecture, PDO, dan interaksi basis data relasional.
    *   Pemahaman dasar protokol HTTP/1.1 & HTTP/2, RFC 6265 (Cookies), dan TLS.
*   **Tech Stack:** PHP 8.2+, Ext-Sodium, Ext-PDO, Ext-OpenSSL, Composer, PSR-7/PSR-15 (HTTP Message & Handlers), Monolog.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1.  **Menganalisis & Mengidentifikasi (Analysis):** Menemukan celah keamanan tingkat lanjut pada aplikasi PHP modern berbasis OWASP Top 10 (Injection, SSRF, Broken Access Control, Deserialization, Race Conditions, Cryptographic Failures).
2.  **Menerapkan Pola Pertahanan Berlapis (Application):** Mengimplementasikan paradigma *Defense-in-Depth* menggunakan kapabilitas native PHP 8.x, PSR-15 Middleware, serta Libsodium.
3.  **Mendesain Sistem Kriptografi Aman (Synthesis):** Mengonstruksi alur autentikasi, hashing kredensial adaptif (Argon2id), verifikasi tanda tangan digital (HMAC/Ed25519), dan enkripsi data simetris autentikasi (AEAD - ChaCha20-Poly1305 / AES-256-GCM).
4.  **Mengisolasi & Mencegah Eksploitasi Eksekusi (Evaluation):** Membangun mekanisme proteksi SSRF mitigasi *DNS Rebinding*, memvalidasi file uploads berbasis *magic bytes* & stream parsing, serta meniadakan *Insecure Deserialization*.
5.  **Menstandardisasi Konfigurasi Hardening (Synthesis):** Mengonfigurasi `php.ini` production-grade, HTTP Content Security Policy (CSP Level 3), dan secure session isolation untuk deployment high-concurrency.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari "Reactive Patching" ke "Zero Trust by Design"
Defensive Security Engineering bukan sekadar memasang validasi *if-else* setelah serangan terjadi. Dalam arsitektur PHP modern, setiap input eksternal—mulai dari `$_GET`, `$_POST`, `$_SERVER`, header HTTP, hingga payload webhook pihak ketiga—harus diasumsikan korup dan dirancang untuk membahayakan sistem (*Guilty until proven innocent*).

```
   ┌─────────────────────────────────────────────────────────────┐
   │                  PARADIGMA DEFENSIVE                        │
   ├──────────────────────────────┬──────────────────────────────┤
   │ TRADISIONAL / NAIF           │ ZERO TRUST / DEFENSIVE ENG   │
   ├──────────────────────────────┼──────────────────────────────┤
   │ Sanitasi di pintu keluar     │ Validasi ketat di batas (IO) │
   │ Mengandalkan WAF eksternal   │ Defense-in-Depth (Layered)   │
   │ "Blacklisting" kata kunci    │ "Whitelisting" ketat (Enums) │
   │ Implicit type casting        │ Strict Typing & Value Objects│
   │ Optimis terhadap upstream IO │ Asumsi IO tidak tepercaya    │
   └──────────────────────────────┴──────────────────────────────┘
```

### Prinsip Inti Defensive Engineering:
1.  **Defense-in-Depth (Pertahanan Berlapis):** Kerentanan pada satu lapisan (misal: bypass WAF) harus dinetralkan oleh lapisan berikutnya (misal: Middleware validasi, lalu Typed Data Transfer Objects, lalu Prepared Statements).
2.  **Principle of Least Privilege (Hak Akses Minimal):** Worker PHP-FPM tidak boleh memiliki akses *write* ke direktori kode sumber; kredensial database aplikasi web tidak boleh memiliki hak `DROP`, `ALTER`, atau `SUPER`.
3.  **Fail-Safe Defaults:** Jika proses parsing, otorisasi, atau validasi kriptografi menghadapi ambiguitas atau kegagalan tak terduga, sistem harus secara *default* menolak akses (*Deny by Default*), bukan melanjutkan eksekusi.
4.  **Complete Mediation:** Setiap akses ke entitas privat atau operasi sensitif harus divalidasi ulang otorisasi dan integritasnya secara konstan, menolak dependensi pada *state* sisi klien.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur penanganan HTTP Request modern di bawah arsitektur Defensive Security PHP:

```
[ HTTP REQUEST DARI KLIEN ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│  REVERSE PROXY / EDGE (Nginx / Cloudflare)            │
│  - SSL/TLS Termination (Strict Ciphers)                │
│  - Rate Limiting, DDoS Shield                          │
│  - Normalisasi Jalur URI & Header Sanitization         │
└──────────────────────────┬─────────────────────────────┘
                           │ FastCGI Unix Domain Socket
                           ▼
┌────────────────────────────────────────────────────────┐
│  PHP RUNTIME LAYER (php.ini Hardened)                  │
│  - disable_functions (exec, passthru, proc_open, dll)  │
│  - open_basedir restricted to application root         │
│  - memory_limit, max_execution_time limits             │
└──────────────────────────┬─────────────────────────────┘
                           │ SAPI Request Processing
                           ▼
┌────────────────────────────────────────────────────────┐
│  PSR-15 MIDDLEWARE PIPELINE (Defensive Boundary)       │
│  ├─ SecurityHeadersMiddleware (HSTS, CSP, FrameOptions)│
│  ├─ IpRateLimiterMiddleware (Sliding Window Redis)     │
│  ├─ CsrfProtectionMiddleware (Synchronizer Token/SameS)│
│  └─ ContentTypeGuardedInputParsingMiddleware           │
└──────────────────────────┬─────────────────────────────┘
                           │ Validated Context & PSR-7 ServerRequest
                           ▼
┌────────────────────────────────────────────────────────┐
│  APPLICATION CORE (Domain & Boundary Protection)       │
│  ├─ DTO Ingestion (Strict Types, Pattern Validation)  │
│  ├─ Value Objects Enforcement (Immutable Domain Rules) │
│  ├─ RBAC / ABAC Contextual Authorization Evaluation    │
│  └─ Cryptographic Verification (HMAC, Digital Signatures)
└──────────────────────────┬─────────────────────────────┘
                           │ Safe Domain Execution
                           ▼
┌────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE / DATA ACCESS LAYER                    │
│  ├─ PDO Parameterized Statements (Zero Concatenation)  │
│  ├─ Safe Network HTTP Client (SSRF & DNS Guarded)      │
│  └─ Encrypted File Storage Engine (Non-executable dir) │
└────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. PHP Engine Memory Management & Type Juggling
PHP secara internal merepresentasikan variabel melalui struktur C bernama `zval` (Zend Value).
```c
struct _zval_struct {
    zend_value value; // Union: lval, dval, *str, *arr, *obj, dll.
    union {
        struct {
            ZEND_ENDIAN_LOHI_3(
                zend_uchar type,
                zend_uchar type_flags,
                union { ... } u;
            )
        } v;
        uint32_t type_info;
    } u1;
    union { ... } u2;
};
```
Ketika operasi perbandingan longgar (`==`) dieksekusi, Zend Engine memanggil fungsi `zendi_smart_strcmp` atau melakukan *implicit casting* antar union tipe data. Celah keamanan klasik terjadi ketika string hash `"0e12345..."` dibandingkan dengan `"0e67890..."`: keduanya di-cast menjadi `float(0)`, menghasilkan evaluasi `true`. 
*Mitigasi:* Selalu gunakan `declare(strict_types=1);` dan perbandingan identik (`===`), atau fungsi *constant-time comparison* seperti `hash_equals()`.

### 2. Hash Timing Attacks & Constant-Time String Comparison
Operasi perbandingan string standar (`strcmp` atau `===`) pada level CPU akan langsung keluar (*short-circuit*) pada byte pertama yang tidak cocok:
```c
// Representasi konseptual implementasi strcmp() standar di C
while (*s1 && (*s1 == *s2)) {
    s1++;
    s2++;
}
return *(unsigned char *)s1 - *(unsigned char *)s2;
```
Penyerang dapat mengukur selisih waktu respons jaringan dalam skala mikrodetik untuk menebak karakter string rahasia (seperti API token atau signature) byte demi byte.
*Mekanisme Pertahanan:* `hash_equals()` menggunakan algoritma perbandingan konstan:
```c
// Representasi konseptual hash_equals() di Zend Engine
size_t len1 = Z_STRLEN_P(known_string);
size_t len2 = Z_STRLEN_P(user_string);
int result = 0;

if (len1 != len2) {
    return 0; // Kadang divariasikan untuk mencegah leakage panjang, 
              // namun native PHP membandingkan panjang dulu 
              // lalu tetap constant-time terhadap known string.
}
for (size_t i = 0; i < len1; i++) {
    result |= (known_string[i] ^ user_string[i]);
}
return result === 0;
```
Setiap byte XOR dieksekusi tanpa *short-circuiting*, sehingga waktu eksekusi invariant terlepas dari posisi kegagalan karakter.

### 3. Password Hashing Internals (Argon2id vs Bcrypt)
`password_hash()` mengabstraksikan implementasi kriptografis mendalam:
*   **Bcrypt ($2y$):** Berbasis Blowfish cipher. Memiliki limitasi internal: input password dipotong secara diam-diam (*truncated*) pada panjang 72 byte, dan rentan terhadap optimasi perangkat keras ASIC/GPU karena hanya bergantung pada memory yang sangat kecil (4 KB).
*   **Argon2id ($argon2id$):** Pemenang Password Hashing Competition. Mengombinasikan pendekatan *Argon2d* (resisten terhadap GPU cracking via data-dependent memory access) dan *Argon2i* (resisten terhadap side-channel timing attack via data-independent memory access). Mengonsumsi konfigurasi parameter: Memory Cost (`memory_cost`), Time Cost (`time_cost`), dan Parallelism Threads (`threads`).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Server-Side Request Forgery (SSRF) & Mitigasi DNS Rebinding
SSRF terjadi ketika backend server dipaksa melakukan HTTP request ke target yang tidak diinginkan (misal: `http://169.254.169.254/latest/meta-data/` pada AWS atau `http://127.0.0.1:6379` untuk Redis).

**Mekanisme Serangan DNS Rebinding:**
1. Penyerang mengontrol domain `attacker.com`.
2. Backend PHP memvalidasi IP: Resolusi pertama `attacker.com` mengembalikan `198.51.100.1` (IP publik aman). Validasi lolos.
3. Backend PHP melakukan cURL request menggunakan URL string `https://attacker.com/data`.
4. DNS TTL domain penyerang diatur ke `0` detik. Saat cURL mengeksekusi koneksi TCP, sistem operasi me-resolve ulang domain `attacker.com`.
5. DNS Server penyerang kini mengembalikan `127.0.0.1`.
6. cURL terhubung ke loopback internal dan mengeksekusi request!

**Formula Mitigasi:** Pinning IP Address sebelum transmisi protokol. Resolusi DNS dilakukan secara mandiri, divalidasi terhadap range IP privat/reserved (CIDR checks), kemudian koneksi TCP dipaksa mengikat (*bind/connect*) secara langsung ke IP yang sudah diverifikasi, menimpa resolusi HTTP Host header via socket wrapper atau opsi `CURLOPT_RESOLVE`.

### 2. Insecure Deserialization vs Native Structured Formats
Fungsi `unserialize()` pada PHP memulihkan representasi teks dari object graph ke dalam memory. Jika kelas yang bersangkutan (atau dependency di vendor autoload) memiliki "magic methods" (`__destruct`, `__wakeup`, `__toString`), penyerang dapat menyusun *POP Chain (Property Oriented Programming)* untuk mengeksekusi arbitrary code (RCE) tanpa perlu kode aplikasi memiliki celah eksekusi langsung.
*Aturan Mutlak Defensive:*
*   Jangan pernah menggunakan `unserialize()` untuk payload eksternal.
*   Gunakan `json_decode()` dengan flag `JSON_THROW_ON_ERROR`.
*   Jika serialization objek biner mutlak diperlukan antar-sistem tepercaya, gunakan enkripsi terotentikasi (Signed/Encrypted Payload).

### 3. Context-Aware Output Escaping
Banyak insinyur berasumsi bahwa `htmlspecialchars()` menyelesaikan seluruh masalah XSS. Ini adalah asumsi keliru. Karakter yang berbahaya bergantung pada *konteks rendering*:

| Konteks | Bahaya | Penanganan yang Tepat |
| :--- | :--- | :--- |
| **HTML Body** (`<div>$input</div>`) | `<script>`, `<img>` | `htmlspecialchars($str, ENT_QUOTES \| ENT_SUBSTITUTE, 'UTF-8')` |
| **HTML Attribute** (`<input value="$input">`) | Quotes breakout, inline events (`onload=`) | Escaping quotes & context validation; tolak karakter control |
| **JavaScript Variable** (`<script>let a = '$input';</script>`) | Script injection, newline syntax break | `json_encode($data, JSON_HEX_TAG \| JSON_HEX_APOS \| JSON_HEX_QUOT \| JSON_HEX_AMP)` |
| **URI Context** (`<a href="$input">`) | `javascript:...`, `data:...` scheme | Validasi skema (hanya `http`, `https`), lalu `urlencode()` |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi modul defensive engineering fundamental: sebuah library sanitasi, validasi, dan cryptographic engine mandiri yang mematuhi standar keamanan PHP 8.2+.

```php
<?php

declare(strict_types=1);

namespace App\Security;

use SensitiveParameter;
use InvalidArgumentException;
use RuntimeException;

final class DefensiveCore
{
    private const ALLOWED_HASH_ALGO = PASSWORD_ARGON2ID;
    private const ARGON2_MEMORY_COST = 65536; // 64 MB
    private const ARGON2_TIME_COST = 4;       // 4 iterasi
    private const ARGON2_THREADS = 1;         // 1 thread (skalabilitas web FPM)

    /**
     * Hashing password dengan algoritma Argon2id dan memory cost adaptif.
     */
    public function hashPassword(#[SensitiveParameter] string $plainPassword): string
    {
        if (strlen($plainPassword) > 4096) {
            throw new InvalidArgumentException('Ukuran password melebihi ambang batas.');
        }

        $hash = password_hash($plainPassword, self::ALLOWED_HASH_ALGO, [
            'memory_cost' => self::ARGON2_MEMORY_COST,
            'time_cost'   => self::ARGON2_TIME_COST,
            'threads'     => self::ARGON2_THREADS,
        ]);

        if ($hash === false) {
            throw new RuntimeException('Gagal mengeksekusi hashing password secara aman.');
        }

        return $hash;
    }

    /**
     * Verifikasi password konstan terhadap timing attacks.
     */
    public function verifyPassword(
        #[SensitiveParameter] string $plainPassword,
        string $knownHash
    ): bool {
        if (!password_verify($plainPassword, $knownHash)) {
            return false;
        }

        return true;
    }

    /**
     * Memeriksa apakah hash perlu di-rehash karena rotasi policy biaya komputasi.
     */
    public function needsRehash(string $knownHash): bool
    {
        return password_needs_rehash($knownHash, self::ALLOWED_HASH_ALGO, [
            'memory_cost' => self::ARGON2_MEMORY_COST,
            'time_cost'   => self::ARGON2_TIME_COST,
            'threads'     => self::ARGON2_THREADS,
        ]);
    }

    /**
     * Context-Aware Output Escaping untuk HTML Context.
     */
    public function escapeHtml(string $untrustedData): string
    {
        return htmlspecialchars(
            $untrustedData,
            ENT_QUOTES | ENT_SUBSTITUTE | ENT_HTML5,
            'UTF-8'
        );
    }

    /**
     * Context-Aware JSON/JS String Ingestion Escaping.
     */
    public function escapeForJavaScript(mixed $untrustedData): string
    {
        $encoded = json_encode(
            $untrustedData,
            JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_THROW_ON_ERROR
        );

        return $encoded;
    }

    /**
     * Constant-time signature verification untuk token/HMAC.
     */
    public function verifySignature(string $expected, string $actual): bool
    {
        return hash_equals($expected, $actual);
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 3: `declare(strict_types=1);`**
    Memaksa Zend Engine untuk menolak koersi tipe implisit. Parameter bertipe `string` tidak akan menerima integer, boolean, atau array secara serampangan. Mencegah kerentanan type juggling pada fungsi keamanan.
*   **Baris 10: `use SensitiveParameter;`**
    Atribut native PHP 8.2+. Memastikan variabel yang ditandai (seperti password plaintext) nilainya disamarkan (`Object(SensitiveParameterValue)`) dalam *stack trace* saat exception runtime terjadi, sehingga credential tidak bocor ke log agregator (Bugsnag, Sentry, CloudWatch).
*   **Baris 14–17: Konstanta Konfigurasi Argon2id**
    Konfigurasi `memory_cost` 64MB dan `time_cost` 4 dipilih secara empiris untuk menghambat paralelisasi cracking GPU, seraya membatasi latensi backend maksimum sekitar 150-250ms per request autentikasi pada server produksi modern.
*   **Baris 24–26: Password Length Check**
    Validasi batas panjang string 4096 byte. Meskipun Argon2 tidak memiliki batas 72 byte seperti Bcrypt, input password yang luar biasa masif (misal: 10 megabyte string) dapat dimanfaatkan untuk DoS (*Denial of Service*) CPU exhaust pada server backend.
*   **Baris 42–49: `verifyPassword`**
    Fungsi internal `password_verify` secara implisit menggunakan perbandingan *constant-time* untuk mencegah side-channel timing attack pada pencocokan hash.
*   **Baris 63–71: `escapeHtml` dengan Flags Ketat**
    `ENT_QUOTES` mengonversi single (`'`) dan double (`"`) quotes. `ENT_SUBSTITUTE` mengganti sequence invalid UTF-8 dengan karakter Unicode pengganti (`\u{FFFD}`) ketimbang mengembalikan string kosong (yang bisa merusak struktur konteks DOM). `ENT_HTML5` menjamin pemetaan entitas sesuai spek HTML modern.
*   **Baris 76–84: `escapeForJavaScript`**
    Flags `JSON_HEX_TAG`, `JSON_HEX_AMP`, `JSON_HEX_APOS`, dan `JSON_HEX_QUOT` mengonversi karakter `<, >, &, ', "` menjadi representasi unicode hex (`\u003C`, dll). Ini mencegah penyerang menutup tag `<script>` atau keluar dari string boundary di JavaScript.
*   **Baris 89–92: `hash_equals($expected, $actual)`**
    Mengeksekusi perbandingan string berbasis time-invariant. Melindungi verifikasi HMAC webhook, API signatures, dan tokens dari remote timing measurement attacks.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Kasus: FinTech Global Webhook & Inbound Fund Transfer Ingestion Engine
Sebuah payment gateway berskala enterprise menghadapi ancaman eksploitasi harian:
1.  **Vendor Webhook Spoofing:** Penyerang memalsukan webhook notifikasi pembayaran sukses dari mitra acquiring bank.
2.  **Server-Side Request Forgery (SSRF) via Receipt Fetcher:** Fitur sistem yang bertugas mengambil e-receipt PDF dari endpoint mitra (`callback_url`) disalahgunakan untuk menargetkan AWS IMDSv2 (`http://169.254.169.254`) dan server Redis internal VPC (`10.0.x.x`).
3.  **Race Condition (Double-Spending):** Eksekusi paralel simultan dari satu transaksi sukses yang memicu settlement kredit ganda ke saldo merchant.

### Strategi Arsitektur Pertahanan:
*   Membangun pipeline verifikasi cryptographic signature (HMAC-SHA256) dengan rotasi secret.
*   Membangun HTTP client *Zero-SSRF* kustom: melakukan validasi skema, DNS manual lookup, filtering IP private/reserved ranges (RFC 1918, RFC 3927, RFC 4193), dan *IP binding transport*.
*   Menghindari Race Condition menggunakan atomic database locking (`SELECT ... FOR UPDATE`) atau Redis Distributed Mutex (Redlock) pada level transaksi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi backend defensif production-grade untuk menangani webhook finansial dan pengambilan data eksternal aman dari SSRF:

```php
<?php

declare(strict_types=1);

namespace App\Security\Webhook;

use SensitiveParameter;
use InvalidArgumentException;
use RuntimeException;

final class SafeHttpClient
{
    /**
     * Mengambil konten URL publik dengan memvalidasi IP (Anti-SSRF).
     */
    public function secureFetch(string $targetUrl, int $timeoutSeconds = 5): string
    {
        $parts = parse_url($targetUrl);
        if ($parts === false || !isset($parts['scheme'], $parts['host'])) {
            throw new InvalidArgumentException('Malformed URL structure.');
        }

        // 1. Validasi Skema Mutlak: Hanya izinkan HTTPS
        if (strtolower($parts['scheme']) !== 'https') {
            throw new InvalidArgumentException('Insecure protocol: Hanya HTTPS yang diizinkan.');
        }

        $host = $parts['host'];

        // 2. DNS Resolution Manual
        $resolvedIps = dns_get_record($host, DNS_A + DNS_AAAA);
        if (empty($resolvedIps)) {
            throw new RuntimeException("DNS resolution failed for host: {$host}");
        }

        $targetIp = null;
        foreach ($resolvedIps as $record) {
            $candidateIp = $record['ip'] ?? $record['ipv6'] ?? null;
            if ($candidateIp && $this->isPubliclyRoutableIp($candidateIp)) {
                $targetIp = $candidateIp;
                break;
            }
        }

        if ($targetIp === null) {
            throw new RuntimeException('Target host resolve ke jaringan privat atau terlarang.');
        }

        // 3. Eksekusi Request dengan Pinning Target IP via cURL (Anti-DNS Rebinding)
        $port = $parts['port'] ?? 443;
        $ch = curl_init();

        // Parameter CURLOPT_RESOLVE memetakan host:port:ip secara statis
        $resolveMap = ["{$host}:{$port}:{$targetIp}"];

        curl_setopt_array($ch, [
            CURLOPT_URL            => $targetUrl,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => $timeoutSeconds,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_FOLLOWLOCATION => false, // Nonaktifkan redirect otomatis untuk mencegah redirect SSRF bypass
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_RESOLVE        => $resolveMap,
            CURLOPT_PROTOCOLS      => CURLPROTO_HTTPS, // Hanya izinkan protokol HTTPS
        ]);

        $response = curl_exec($ch);
        $error = curl_error($ch);
        $statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($response === false || $statusCode >= 400) {
            throw new RuntimeException("Fetch error: {$error} (HTTP {$statusCode})");
        }

        return (string) $response;
    }

    /**
     * Memeriksa apakah IP publik dan bukan range reserved/internal.
     */
    private function isPubliclyRoutableIp(string $ip): bool
    {
        $filtered = filter_var(
            $ip,
            FILTER_VALIDATE_IP,
            FILTER_FLAG_IPV4 | FILTER_FLAG_IPV6 | 
            FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE
        );

        if ($filtered === false) {
            return false;
        }

        // AWS/Cloud IMDSv2 link-local block eksplisit (169.254.0.0/16)
        if (str_starts_with($ip, '169.254.')) {
            return false;
        }

        return true;
    }
}

final class WebhookSignatureValidator
{
    /**
     * Validasi HMAC SHA-256 Webhook Payload.
     */
    public function validatePayload(
        string $payloadJson,
        string $incomingSignature,
        #[SensitiveParameter] string $secretKey
    ): bool {
        if (empty($incomingSignature) || empty($payloadJson)) {
            return false;
        }

        $calculatedSignature = hash_hmac('sha256', $payloadJson, $secretKey);

        // Constant-time execution memitigasi timing attack
        return hash_equals($calculatedSignature, $incomingSignature);
    }
}

final class PaymentProcessor
{
    public function __construct(
        private readonly \PDO $pdo,
        private readonly SafeHttpClient $httpClient,
        private readonly WebhookSignatureValidator $validator
    ) {}

    /**
     * Pemrosesan transaksi idempotent & race-condition proof.
     */
    public function processWebhook(
        string $rawPayload,
        string $signature,
        #[SensitiveParameter] string $webhookSecret
    ): void {
        // 1. Verifikasi Signature Cryptographic Terlebih Dahulu
        if (!$this->validator->validatePayload($rawPayload, $signature, $webhookSecret)) {
            throw new RuntimeException('Unauthorized webhook signature.');
        }

        // 2. Decode JSON secara ketat
        $data = json_decode($rawPayload, true, 512, JSON_THROW_ON_ERROR);

        $transactionId = $data['transaction_id'] ?? null;
        $receiptUrl = $data['receipt_url'] ?? null;

        if (!$transactionId || !is_string($transactionId)) {
            throw new InvalidArgumentException('Invalid transaction ID.');
        }

        // 3. Database Mutex via Pessimistic Locking dalam Transaksi
        $this->pdo->beginTransaction();

        try {
            $stmt = $this->pdo->prepare(
                'SELECT status, amount FROM transactions WHERE id = :id FOR UPDATE'
            );
            $stmt->execute(['id' => $transactionId]);
            $transaction = $stmt->fetch(\PDO::FETCH_ASSOC);

            if (!$transaction) {
                throw new RuntimeException('Transaction not found.');
            }

            if ($transaction['status'] === 'SETTLED') {
                // Idempotensi: Payload sudah pernah diproses sebelumnya
                $this->pdo->rollBack();
                return;
            }

            // 4. Pengambilan receipt PDF dengan anti-SSRF client jika URL disediakan
            if ($receiptUrl && is_string($receiptUrl)) {
                $receiptContent = $this->httpClient->secureFetch($receiptUrl);
                // Lakukan validasi file content & simpan ke storage terlindungi...
            }

            // 5. Update Status Transaksi
            $updateStmt = $this->pdo->prepare(
                'UPDATE transactions SET status = :status, updated_at = NOW() WHERE id = :id'
            );
            $updateStmt->execute([
                'status' => 'SETTLED',
                'id'     => $transactionId
            ]);

            $this->pdo->commit();
        } catch (\Throwable $e) {
            $this->pdo->rollBack();
            throw $e;
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pendekatan / Algoritma | Kelebihan | Kelemahan / Trade-off | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **Argon2id** | Ketahanan tertinggi terhadap serangan GPU/ASIC dan Side-Channel. | Membutuhkan alokasi memori server yang signifikan (misal: 64MB/thread). Rentan DoS jika parameter terlalu tinggi. | Standar hashing password modern (NIST & OWASP) untuk user credentials. |
| **Bcrypt ($2y$)** | Kompatibilitas universal, footprint memori minimal (4KB). | Password terpotong pada 72 byte. Kurang resisten terhadap modern GPU clusters dibanding Argon2. | Sistem legacy atau resource-constrained container environments. |
| **Sodium Crypto (libsodium)** | Modern, safe API defaults (misal: `crypto_secretbox`), terlindungi secara native dari memory leakage. | Binary payload output memerlukan encoding (base64), API kurva belajar spesifik. | Enkripsi data simetris aplikasi (AEAD), digital signatures (Ed25519). |
| **OpenSSL Ext** | Sangat fleksibel, mendukung semua algoritma kriptografi klasik (AES-GCM, RSA). | API rawan kesalahan konfigurasi manual (salah inisialisasi IV, mode ECB yang rentan). | Integrasi enterprise dengan sertifikat X.509, CMS/PKCS#7. |
| **Pessimistic Locking (`FOR UPDATE`)** | Menjamin integritas data absolut terhadap race condition di DB. | Mengunci baris data (lock contention), menurunkan throughput pada transaksi tinggi. | Alur perbankan, mutasi saldo, alokasi inventaris terbatas. |
| **Optimistic Locking (Versioning)** | Skalabilitas tinggi, tidak mengunci row secara eksklusif. | Request akan gagal dan butuh alur *retry* jika tabrakan konkuren masif. | Profil pengguna, update dokumen kolaboratif. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Type Juggling Vulnerabilities pada `in_array` dan `switch`
```php
// CONTOH RENTAN
$allowedRoles = ['admin', 'manager', 'editor'];
$userRole = 0; // Integer yang dikirim via manipulated JSON

if (in_array($userRole, $allowedRoles)) { 
    // Mengembalikan TRUE pada PHP versi lama, atau jika loose comparison terjadi!
    // PHP membandingkan (0 == 'admin'), string dikonversi ke integer 0.
    grantSuperAdminAccess();
}

// PERBAIKAN DEFENSIVE
if (in_array($userRole, $allowedRoles, true)) { // Parameter ketiga STRICT = true
    grantSuperAdminAccess();
}
// Atau gunakan PHP 8 match expression:
$isAuthorized = match($userRole) {
    'admin', 'manager', 'editor' => true,
    default => false,
};
```

### 2. DNS Rebinding via Redirects
Bahkan jika endpoint awal divalidasi aman, server upstream dapat merespons dengan HTTP Redirect 302:
```
Location: http://169.254.169.254/latest/meta-data/
```
Jika HTTP Client Anda mengaktifkan `CURLOPT_FOLLOWLOCATION => true`, cURL akan mengeksekusi request berikutnya ke alamat berbahaya tanpa melalui layer filter awal.
*Mitigasi:* Selalu matikan auto-redirect (`CURLOPT_FOLLOWLOCATION = false`), atau parse setiap header `Location` secara manual melalui fungsi validasi IP sebelum request lanjutan dieksekusi.

### 3. File Upload Bypass via Magic Bytes Mismatch
Memvalidasi ekstensi file (`.jpg`) dan MIME type dari client (`$_FILES['file']['type']`) sangat berbahaya karena header tersebut sepenuhnya berada dalam kendali penyerang. Penyerang dapat mengunggah file `exploit.php` dengan nama `exploit.jpg` dan MIME `image/jpeg`.
*Mitigasi:* Baca *magic bytes* secara aktual menggunakan ekstensi `fileinfo` (`finfo_open`) dan lakukan proses re-encoding gambar (menggunakan GD atau Imagick) untuk melucuti payload metadata PHP tersembunyi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Kesalahan: Mengandalkan `strip_tags()` untuk Pencegahan XSS
```php
// SALAH DAN BERBAHAYA
$output = strip_tags($_GET['comment']); 
// Penyerang mengirim: <img src="x" onerror="alert(1)"> -> Atribut event handler tetap lolos!
// Atau: <body onload=alert(1)> jika strip_tags dikonfigurasi dengan tags tertentu.

// BENAR
$output = htmlspecialchars($_GET['comment'], ENT_QUOTES | ENT_SUBSTITUTE | ENT_HTML5, 'UTF-8');
```

### 2. Kesalahan: Mempercayai `$_SERVER['HTTP_X_FORWARDED_FOR']`
```php
// SALAH: Penyerang bisa menyuntikkan IP palsu untuk bypass rate limiter
$clientIp = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? $_SERVER['REMOTE_ADDR'];

// BENAR: Validasi IP hanya dari Trusted Reverse Proxies yang diketahui
final class ClientIpResolver
{
    private const TRUSTED_PROXIES = ['10.0.0.100', '10.0.0.101'];

    public static function getRealIp(array $serverVars): string
    {
        $remoteAddr = $serverVars['REMOTE_ADDR'] ?? '127.0.0.1';

        if (!in_array($remoteAddr, self::TRUSTED_PROXIES, true)) {
            return $remoteAddr; // Jika bukan request dari load balancer tepercaya, abaikan header forwarding!
        }

        if (isset($serverVars['HTTP_X_FORWARDED_FOR'])) {
            $ips = array_map('trim', explode(',', $serverVars['HTTP_X_FORWARDED_FOR']));
            return $ips[0]; // IP klien sebenarnya berada di posisi pertama
        }

        return $remoteAddr;
    }
}
```

### 3. Kesalahan: Menggunakan `md5()` atau `sha1()` untuk Token Keamanan
MD5 dan SHA-1 cepat dihitung secara komputasi dan rentan terhadap tabrakan (*collision*). Gunakan `random_bytes()` untuk generasi cryptographically secure pseudo-random bytes (CSPRNG).

```php
// SALAH
$token = md5(uniqid((string)mt_rand(), true));

// BENAR
$token = bin2hex(random_bytes(32)); // 256 bits of cryptographically secure entropy
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Typing di Setiap Berkas:** Pastikan baris pertama setiap file PHP selalu `declare(strict_types=1);`.
2.  **Immutability untuk Keamanan Domain:** Definisikan Data Transfer Objects (DTO) dan Value Objects sebagai `readonly class` guna mencegah mutasi state tidak sah di tengah alur eksekusi aplikasi.
3.  **Sanitize Boundary, Escape on Output:**
    *   *Input:* Validasi struktur, tipe data, dan panjang (*Whitelisting*). Jangan ubah data mentah jika tidak diperlukan.
    *   *Output:* Escape data sesuai dengan medium rendering (HTML, JS, SQL, Shell CLI).
4.  **PHP Static Analysis Security Testing (SAST):**
    Jalankan PHPStan atau Psalm pada level analisis tertinggi (`level: max` atau `level: 8`) yang dilengkapi plugin keamanan seperti `vimeo/psalm-plugin-security` untuk mendeteksi *tainted data flows*.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

Mekanisme keamanan seperti hashing intensif dapat membuka celah DoS bila tidak diatur dengan cermat.

```
                      KURVA BIAYA KOMPUTASI ARGON2ID
  Tinggi ┌                                            
         │                                       /
  K      │                                      / (Eksploitasi DoS)
  O      │                                     /  
  M      │                              . - - * (Ambang Batas Optimum)
  P      │                      . - '
  U      │              . - ' 
  T      │      . - ' 
  A      │ . - ' 
  S      │─────────────────────────────────────
  I      └───────────────────────────────────────────► Rendah
         Rendah            LATENSI / MEMORI             Tinggi
```

### Panduan Optimasi Keamanan:
*   **Benchmarking Argon2id:** Tentukan konfigurasi di mana satu proses hashing password menghabiskan waktu sekitar **150ms – 250ms** pada core CPU server produksi. Nilai lebih rendah membuka celah brute-force, nilai lebih tinggi menurunkan ketersediaan (*availability*) PHP-FPM pool saat ada gelombang login massal.
*   **Regex Denial of Service (ReDoS) Prevention:** Hindari ekspresi reguler yang memiliki *catastrophic backtracking* (contoh: `(a+)+$`). Atur batasan backtracking internal PHP:
    ```ini
    pcre.backtrack_limit=100000
    pcre.recursion_limit=100000
    ```
*   **Streaming File Parsing:** Jangan membaca file utuh berukuran gigabyte ke dalam memori aplikasi menggunakan `file_get_contents()` untuk validasi. Gunakan stream pointer (`fopen`, `fread` secara bertahap) untuk memvalidasi magic bytes.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Production-Grade `php.ini` Hardening Template
Terapkan direktif berikut pada environment produksi untuk memangkas *attack surface*:

```ini
; Menonaktifkan eksposur identitas runtime PHP pada header HTTP Response
expose_php = Off

; Mencegah eksekusi arbitrary sistem via fungsi-fungsi berbahaya
disable_functions = exec,passthru,shell_exec,system,proc_open,proc_close,proc_nice,proc_terminate,popen,pclose,curl_multi_exec,parse_ini_file,show_source

; Matikan pelaporan error ke layar; salurkan hanya ke internal system logger
display_errors = Off
display_startup_errors = Off
log_errors = On
error_reporting = E_ALL & ~E_DEPRECATED & ~E_STRICT

; Isolasi akses berkas PHP hanya ke direktori aplikasi
open_basedir = "/var/www/app:/tmp"

; Larang registrasi stream eksternal pada fungsi file
allow_url_fopen = Off
allow_url_include = Off

; Hardening Parameter Session Kuki
session.use_strict_mode = 1
session.cookie_httponly = 1
session.cookie_secure = 1
session.cookie_samesite = "Strict"
session.use_only_cookies = 1
session.sid_length = 48
session.sid_bits_per_character = 6
```

### Security Headers Middleware Implementation (PSR-15)

```php
<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Psr\Http\Message\ResponseInterface;
use Psr\Http\Message\ServerRequestInterface;
use Psr\Http\Server\MiddlewareInterface;
use Psr\Http\Server\RequestHandlerInterface;

final class SecurityHeadersMiddleware implements MiddlewareInterface
{
    public function process(ServerRequestInterface $request, RequestHandlerInterface $handler): ResponseInterface
    {
        $response = $handler->handle($request);

        return $response
            ->withHeader('X-Frame-Options', 'DENY')
            ->withHeader('X-Content-Type-Options', 'nosniff')
            ->withHeader('Referrer-Policy', 'strict-origin-when-cross-origin')
            ->withHeader('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
            ->withHeader('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload')
            ->withHeader(
                'Content-Security-Policy',
                "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';"
            );
    }
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Sistem logging yang baik harus memberikan jejak audit yang kaya tanpa pernah membocorkan informasi rahasia (*Personally Identifiable Information* (PII) atau Kredensial).

```php
<?php

declare(strict_types=1);

namespace App\Security\Logging;

use Monolog\Processor\ProcessorInterface;
use Monolog\LogRecord;

final class SensitiveDataRedactionProcessor implements ProcessorInterface
{
    private const SENSITIVE_KEYS = [
        'password',
        'secret',
        'token',
        'authorization',
        'credit_card',
        'cvv',
        'pin'
    ];

    public function __invoke(LogRecord $record): LogRecord
    {
        $context = $this->redactArray($record->context);

        return $record->with(context: $context);
    }

    private function redactArray(array $data): array
    {
        foreach ($data as $key => $value) {
            if (is_array($value)) {
                $data[$key] = $this->redactArray($value);
                continue;
            }

            if (is_string($key) && $this->isKeySensitive($key)) {
                $data[$key] = '***REDACTED***';
            }
        }

        return $data;
    }

    private function isKeySensitive(string $key): bool
    {
        $normalizedKey = strtolower($key);
        foreach (self::SENSITIVE_KEYS as $sensitive) {
            if (str_contains($normalizedKey, $sensitive)) {
                return true;
            }
        }
        return false;
    }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### The Defensive Engineer's Golden Rules:

```
[ INPUT BOUNDARY ]
  ├── 1. Validasi tipe secara ketat: declare(strict_types=1).
  ├── 2. Jangan pernah percaya ekstensi berkas atau Content-Type client.
  └── 3. Gunakan filter_var() dengan flags lengkap (NO_PRIV_RANGE/NO_RES_RANGE).

[ INTERNAL PROCESSING ]
  ├── 4. Hashing password: password_hash(..., PASSWORD_ARGON2ID).
  ├── 5. Perbandingan string rahasia: Wajib hash_equals().
  ├── 6. Nilai sensitif: Berikan atribut #[SensitiveParameter].
  └── 7. Format transmisi internal: Gunakan JSON ketat; Tinggalkan unserialize().

[ EXTERNAL COMMUNICATION ]
  ├── 8. Anti-SSRF: Resolve IP terlebih dahulu, lalu kunci via CURLOPT_RESOLVE.
  └── 9. Database queries: Gunakan PDO Prepared Statements tanpa konkatenasi.

[ OUTPUT BOUNDARY ]
  ├── 10. HTML Context: htmlspecialchars($val, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').
  └── 11. Headers: Enforce HSTS, CSP Level 3, X-Frame-Options: DENY.
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Tingkat Dasar (Basic)

**Soal 1:** Mengapa kode `$stmt = $pdo->query("SELECT * FROM users WHERE email = '$email'");` rentan meskipun input `$email` telah melewati fungsi `addslashes()`?  
*Jawaban Teknis:* `addslashes()` hanya menambahkan backslash pada karakter tertentu dan tidak menyadari set karakter (*character set encoding*) dari koneksi database (misalnya GBK multi-byte character set injection). Karakter byte tertentu dapat "memakan" backslash tersebut dan membangkitkan single quote valid, menyebabkan SQL Injection. Pendekatan yang benar secara mutlak adalah native parameterized prepared statements via PDO (`prepare()` dan `execute()`).

**Soal 2:** Apa implikasi keamanan dari mengeksekusi `password_hash($password, PASSWORD_BCRYPT)` jika pengguna memasukkan password dengan panjang 120 karakter?  
*Jawaban Teknis:* Algoritma Bcrypt secara internal memiliki limitasi panjang input maksimum sebesar 72 byte. Karakter ke-73 dan seterusnya akan dipotong (*truncated*) secara diam-diam. Akibatnya, dua password yang identik pada 72 karakter pertama namun berbeda di ujungnya akan menghasilkan hash yang sama dan keduanya dapat digunakan untuk login.

**Soal 3:** Apa fungsi dari atribut `#[SensitiveParameter]` yang diperkenalkan pada PHP 8.2?  
*Jawaban Teknis:* Atribut ini mencegah nilai parameter (seperti kata sandi, token otorisasi, atau kunci privat) tercetak dalam bentuk teks mentah pada stack trace ketika terjadi exception. Runtime akan menggantikan representasi nilainya menjadi `Object(SensitiveParameterValue)`.

**Soal 4:** Mengapa fungsi `rand()` atau `mt_rand()` dilarang keras untuk pembuatan token reset password atau cryptographic nonce?  
*Jawaban Teknis:* Keduanya adalah *Linear Congruential / Mersenne Twister Pseudo-Random Number Generators (PRNG)* yang bersifat deterministik dan bukan CSPRNG. Penyerang yang mengamati beberapa output urutan angka dapat merekonstruksi *internal seed state* dan memprediksi token keamanan berikutnya secara presisi.

**Soal 5:** Apa bahaya dari konfigurasi `session.cookie_httponly = 0` pada aplikasi web produksi?  
*Jawaban Teknis:* Memungkinkan cookie session diakses oleh JavaScript sisi klien via API `document.cookie`. Jika aplikasi terkena serangan Cross-Site Scripting (XSS), penyerang dapat secara langsung mencuri session ID pengguna dan membajak sesi aktif (*Session Hijacking*).

---

### Tingkat Menengah (Intermediate)

**Soal 6:** Jelaskan secara teknis skenario eksploitasi timing attack pada verifikasi token API jika pengembang menggunakan operator `$incomingToken === $validToken`, dan bagaimana `hash_equals()` meniadakannya!  
*Jawaban Teknis:* Operator `===` melakukan *short-circuit evaluation*: pemrosesan berhenti seketika pada byte pertama yang tidak cocok. Penyerang dapat mengukur variasi latensi respons server: waktu respons lebih lama mengindikasikan byte tebakan benar pada indeks awal. Dengan ribuan request dan pengukuran presisi mikrodetik, penyerang dapat merekonstruksi token byte per byte. `hash_equals()` menggunakan operasi bitwise XOR pada seluruh panjang byte tanpa *short-circuiting*, sehingga waktu eksekusi selalu konstan.

**Soal 7:** Anda memvalidasi URL menggunakan `filter_var($url, FILTER_VALIDATE_URL)`. Mengapa ini belum memadai untuk mencegah serangan SSRF terhadap endpoint metadata cloud AWS?  
*Jawaban Teknis:* `filter_var()` hanya memvalidasi kesesuaian format sintaks URL (RFC 2396), bukan tujuannya. URL seperti `http://169.254.169.254/latest/meta-data/` adalah URL yang valid secara sintaksis, namun mengarah ke IP Link-Local Instance Metadata Service (IMDS) AWS. Tanpa validasi resolusi IP ke blok non-privat dan non-reserved, server tetap rentan terhadap SSRF.

**Soal 8:** Mengapa mengecek `$_FILES['upload']['type']` adalah prosedur yang sama sekali tidak memiliki nilai keamanan dalam pertahanan file upload?  
*Jawaban Teknis:* Nilai `$_FILES['upload']['type']` diekstraksi langsung dari header HTTP `Content-Type` yang dikirim oleh klien browser. Penyerang dapat menggunakan HTTP client (misal: cURL, Burp Suite) untuk mengirimkan file executable PHP jahat dengan memalsukan header menjadi `Content-Type: image/jpeg`. Pemeriksaan ini tidak mencerminkan isi aktual dari payload berkas.

**Soal 9:** Bagaimana serangan *DNS Rebinding* dapat mem-bypass validasi SSRF yang hanya memeriksa IP di awal pemrosesan kode, dan bagaimana mekanisme pencegahannya di PHP?  
*Jawaban Teknis:* Penyerang mendaftarkan domain dengan DNS TTL 0 detik. Ketika kode memeriksa IP via `gethostbyname()`, DNS server penyerang merespons dengan IP publik (valid). Namun saat fungsi HTTP client (seperti `curl_exec()`) dieksekusi beberapa milidetik kemudian, cURL melakukan resolusi DNS ulang; DNS server penyerang merespons dengan IP lokal (`127.0.0.1`). Pencegahannya adalah mem-pinning IP hasil validasi pertama ke handle cURL menggunakan opsi `CURLOPT_RESOLVE`, sehingga cURL dilarang melakukan query DNS ulang.

**Soal 10:** Jelaskan risiko keamanan dari penggunaan `unserialize()` terhadap string yang diinput oleh pengguna, meskipun kelas aplikasi Anda tidak secara eksplisit memiliki fungsi `eval()`!  
*Jawaban Teknis:* Proses deserialisasi secara otomatis memicu metode *magic* objek PHP (`__wakeup()`, `__destruct()`, `__toString()`). Jika terdapat library pihak ketiga di direktori vendor autoload yang memiliki deklarasi *magic methods* dengan fungsionalitas membaca file, menulis file, atau memanggil fungsi dinamis, penyerang dapat merangkai objek-objek tersebut menjadi *POP Chain (Property-Oriented Programming)* untuk memicu *Remote Code Execution (RCE)* tanpa bergantung pada kode buatan pengembang sendiri.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Project Prompt: Zero-Trust Secure File Upload & Verification Service

#### Instruksi Pengerjaan:
Bangun sebuah service mandiri berbasis PHP 8.2+ bernama `SecureDocumentIngestionService` yang bertugas menerima upload dokumen (PDF & Gambar PNG/JPEG) dengan ketentuan keamanan zero-trust berikut:

1.  **Strict File Inspection Layer:**
    *   Tolak file berdasarkan ekstensi blacklist; gunakan pendekatan *strict whitelist* (hanya `.png`, `.jpg`, `.jpeg`, `.pdf`).
    *   Gunakan `finfo_open(FILEINFO_MIME_TYPE)` untuk memverifikasi MIME type langsung dari stream buffer file.
    *   Implementasikan deteksi *Magic Bytes* biner secara eksplisit (misal: byte signature PDF `%PDF-`, PNG `\x89PNG\r\n\x1a\n`).
2.  **Sanitization & Re-encoding:**
    *   Untuk file gambar, muat ulang gambar ke memory menggunakan library `GD` atau `Imagick`, lalu export kembali ke format target untuk melucuti *steganographic PHP payloads* atau metadata EXIF jahat.
    *   Simpan file dengan UUID v4 yang baru dibuat secara kriptografis (`bin2hex(random_bytes(16))`), jangan pernah mempertahankan nama file asli dari user.
3.  **Storage Isolation:**
    *   Tulis file ke direktori di luar document root web server (`open_basedir` protected).
    *   Buat file `.htaccess` atau proteksi Nginx agar direktori penyimpanan tidak dapat mengeksekusi script PHP secara langsung (`php_flag engine off`).
4.  **Audit Trail Logging:**
    *   Catat hash SHA-256 dari setiap file yang berhasil diunggah beserta metadata IP pengunggah (menggunakan real IP resolver aman) ke dalam structured security log JSON.

#### Kriteria Keberhasilan (Verification):
*   Eksekusi pengujian dengan mengunggah shell PHP tersembunyi di dalam komentar metadata EXIF gambar JPEG: sistem harus membersihkan metadata tersebut atau menolak berkas.
*   Unggah file teks berekstensi `.pdf`: sistem harus menolak karena ketidakcocokan magic bytes.
*   Analisis kode Anda dengan PHPStan level 8: tidak boleh ada peringatan (*zero errors*).
*   Seluruh parameter sensitif tidak boleh tercetak pada stack trace saat runtime error disimulasikan.