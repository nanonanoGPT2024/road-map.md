# BAB 06: Quiz, Challenge, & Knowledge Check
**Defensive Security Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Pemisahan Data dan Kode pada SQL Injection
Jelaskan secara mendalam dari perspektif *Compiler* RDBMS mengapa mekanisme *Prepared Statements* (menggunakan PDO dengan `PDO::ATTR_EMULATE_PREPARES => false`) menjamin kekebalan mutlak terhadap injeksi SQL tipe *literal data*, sedangkan fungsi *escaping* manual seperti `addslashes()` atau `mysqli_real_escape_string()` tetap rentan terhadap kondisi tertentu (seperti *character encoding mismatch* atau *unquoted numeric literals*).

### Soal 1.2: Cryptographic Hashing vs Fast Hashing
Mengapa algoritma *cryptographic hash* cepat seperti SHA-256 atau SHA-3 sangat dilarang digunakan untuk *password storage*, sekalipun telah ditambahkan *salt* statis/dinamis yang panjang? Analisis perbedaan arsitektur pemrosesan hardware (ASIC, FPGA, GPU) antara algoritma *cryptographic hash* murni dan *memory-hard password derivation functions* seperti Argon2id atau Bcrypt.

### Soal 1.3: Kontekstual Output Encoding pada XSS
Mengapa fungsi `htmlspecialchars($input, ENT_QUOTES | ENT_HTML5, 'UTF-8')` gagal melindungi aplikasi dari serangan *Cross-Site Scripting* (XSS) apabila variabel tersebut di-render di dalam atribut HTML tertentu (contoh: `<a href="<?= $url ?>">`), di dalam konteks JavaScript (`<script>var id = "<?= $id ?>";</script>`), atau di dalam style attribute (`<div style="background: <?= $style ?>;">`)? Jelaskan aturan *Context-Aware Escaping* yang benar untuk masing-masing zona konteks tersebut.

### Soal 1.4: Mitigasi CSRF dan Dinamika Cookie Attribute
Bandingkan efektivitas proteksi serangan *Cross-Site Request Forgery* (CSRF) menggunakan *Synchronizer Token Pattern* versus pemanfaatan atribut `SameSite=Strict` dan `SameSite=Lax` pada *Session Cookie*. Dalam skenario interaksi modern apa saja `SameSite=Lax` masih membuka celah serangan (misalnya: *top-level navigation vulnerabilities* atau *GET-based state changes*)?

### Soal 1.5: Anatomi Server-Side Request Forgery (SSRF)
Mengapa validasi URL menggunakan `filter_var($url, FILTER_VALIDATE_URL)` tidak memberikan pertahanan yang memadai terhadap serangan SSRF? Jelaskan bahaya representasi IP alternatif (misalnya: *Hexadecimal*, *Dotted Integer*, *Octal*, *0.0.0.0*) dan jelaskan fenomena *DNS Rebinding* yang dapat membypass validasi alamat *private/loopback* IP (RFC 1918) pada lapisan aplikasi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Zend Engine Serialization & POP Chain Execution
Uraikan alur kerja internal *Zend Engine* saat mengeksekusi `unserialize()` pada *untrusted input*. Bagaimana sebuah rantai objek (*Property-Oriented Programming* / POP Chain) memanfaatkan metode-metode magis (`__destruct`, `__wakeup`, `__toString`) dari *class-class* yang sudah dimuat oleh *Composer autoloader* untuk mencapai *Remote Code Execution* (RCE)? Mengapa parsing JSON murni (`json_decode`) ke dalam DTO (*Data Transfer Object*) lebih aman secara fundamental?

### Soal 2.2: Side-Channel Timing Attacks pada String Comparison
Perhatikan kode berikut:
```php
if ($userSubmittedToken === $secureAuthToken) {
    // Authorized action
}
```
Jelaskan bagaimana operator `===` atau fungsi `strcmp()` pada C-level implementasi PHP melakukan optimasi *early-exit* (berhenti pada *byte* pertama yang tidak cocok). Bagaimana penyerang dapat mengeksploitasi perbedaan latensi dalam skala mikrosekon/nanosekon untuk menebak nilai token *byte demi byte*, dan bagaimana fungsi `hash_equals()` menghentikan serangan ini pada level komputasi CPU?

### Soal 2.3: Validasi File Upload dan Mitigasi Polyglot
Jika sebuah sistem mengandalkan `mime_content_type()` (atau ekstensi `finfo`) dan memeriksa ekstensi file menggunakan `pathinfo($filename, PATHINFO_EXTENSION)`, jelaskan bagaimana penyerang dapat menyusupkan webshell PHP yang disembunyikan di dalam *header* gambar GIF/JPEG (*polyglot file*). Sebutkan rancangan komprehensif untuk *File Upload Pipeline* yang aman dari serangan eksekusi kode langsung pada web server berbasis NGINX + PHP-FPM.

### Soal 2.4: Eksploitasi PHP Stream Wrappers dan Arbitrary File Inclusion
Jelaskan bagaimana penyerang memanipulasi *stream wrappers* bawaan PHP seperti `php://filter/convert.base64-encode/resource=...` atau `phar://` dalam fungsi manipulasi file (`file_get_contents`, `include`, `file_exists`). Mengapa pemanggilan `file_exists()` atau `is_readable()` terhadap input dari pengguna yang diawali dengan skema `phar://` pada PHP versi terdahulu (sebelum PHP 8.0) dapat memicu deserialisasi objek secara implisit?

### Soal 2.5: Session Fixation & Hijacking pada Arsitektur Terdistribusi
Pada arsitektur aplikasi berbasis *microservices* atau *multi-instance autoscaling* dengan session handler berbasis Redis:
1. Mengapa `session_regenerate_id(true)` mutlak dieksekusi secara tepat saat privilege user dinaikkan (misalnya dari *guest* menjadi *authenticated*)?
2. Bagaimana Anda mengamankan transmisi ID sesi dari serangan *Man-In-The-Middle* dan manipulasi *Client-Side Script* jika token sesi diteruskan melalui cookie (`HttpOnly`, `Secure`, `SameSite`) versus jika diteruskan melalui `Authorization: Bearer` header?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Zero-Day SSRF pada Microservice Webhook Engine
Sebuah platform SaaS Enterprise memiliki fitur "Webhook Delivery & Integration Hub" di mana pelanggan dapat mendaftarkan URL endpoint pihak ketiga untuk menerima notifikasi *event* transaksi via HTTP POST. Sistem ini dibangun dengan PHP 8.2 dan menggunakan GuzzleHTTP.

Suatu hari, tim Security Operations Center (SOC) mendeteksi lonjakan trafik anomali dari server aplikasi internal menuju endpoint internal AWS Metadata Service (`http://169.254.169.254/latest/meta-data/`) dan server Redis internal (`10.0.4.15:6379`), yang mengakibatkan kebocoran kredensial *IAM Role* dan modifikasi *cache* cluster.

**Pertanyaan Diagnostik & Arsitektur:**
1. Apa kesalahan arsitektur validasi URL yang paling mungkin terjadi pada kode PHP sebelum *request* dikirim oleh GuzzleHTTP?
2. Mengapa melakukan `gethostbyname($domain)` di level PHP sebelum melakukan request menggunakan GuzzleHTTP justru memicu celah *Time-of-Check to Time-of-Use* (TOCTOU) via *DNS Rebinding*?
3. Rancanglah solusi arsitektur pertahanan *Defense-in-Depth* (kombinasi network isolation, konfigurasi cURL/Guzzle socket handler, dan validasi IP) untuk mengisolasi request webhook secara total dari jaringan internal.

---

### Skenario B: Race Condition pada Point-of-Sale / Dompet Digital (TOCTOU)
Sebuah platform e-commerce menyelenggarakan *Flash Sale* dengan volume transaksi mencapai 15.000 RPS. Pengguna dapat menggunakan saldo dompet digital untuk checkout. Tim Finance menemukan indikasi *double-spending*: saldo seorang pengguna terpotong satu kali, namun pengguna tersebut berhasil membuat dua atau tiga order sekaligus dengan saldo yang sama.

Kode controller lama diidentifikasi sebagai berikut:
```php
public function deductBalance(int $userId, int $amount): bool
{
    $wallet = $this->walletRepo->findByUserId($userId); // SELECT * FROM wallets WHERE user_id = ?
    
    if ($wallet->getBalance() >= $amount) {
        $newBalance = $wallet->getBalance() - $amount;
        $this->walletRepo->updateBalance($userId, $newBalance); // UPDATE wallets SET balance = ? WHERE user_id = ?
        return true;
    }
    
    return false;
}
```

**Pertanyaan Diagnostik & Arsitektur:**
1. Uraikan secara presisi bagaimana *concurrency race condition* terjadi pada level transaksi database dan proses PHP-FPM worker multi-threaded/multi-process.
2. Mengapa menempatkan blok kode tersebut di dalam transaksi standar (`BEGIN TRANSACTION` ... `COMMIT`) tanpa pengaturan isolasi atau penguncian tertentu **tidak** menyelesaikan masalah pada database MySQL InnoDB dengan default isolation level *REPEATABLE READ*?
3. Sajikan dua alternatif perbaikan arsitektural:
   - Alternatif 1: Solusi database-level native (Gunakan *Pessimistic Locking* atau *Atomic Operation*).
   - Alternatif 2: Solusi aplikasi terdistribusi (Gunakan Redis Redlock / Distributed Mutex). Jelaskan *trade-off* latensi dan kompleksitas dari kedua opsi tersebut.

---

### Skenario C: Migrasi Sistem Kriptografi Autentikasi Warisan (Legacy Cryptographic Migration)
Sebuah platform media sosial enterprise dengan 20 juta pengguna aktif masih menggunakan skema hashing kuno `md5($password . $salt)` pada basis data mereka. Manajemen menuntut sistem di-upgrade ke standar keamanan tertinggi saat ini: **Argon2id**. 

Namun, ada batasan sistem:
- Password plaintext pengguna tidak pernah disimpan.
- Sistem tidak boleh memaksa seluruh pengguna melakukan *reset password massal* (karena akan merusak metrik retensi bisnis).
- Kapasitas CPU server autentikasi terbatas (tidak boleh terjadi *denial of service* internal akibat komputasi Argon2id yang berlebihan saat jam sibuk/peak traffic).

**Pertanyaan Diagnostik & Arsitektur:**
1. Rancang pola transisi hashing (*Transparent Re-hashing*) menggunakan API native PHP `password_verify()` dan `password_needs_rehash()`. Bagaimana logika flow autentikasi menangani verifikasi terhadap password bertipe MD5 lama dan secara transparan mengonversinya menjadi Argon2id saat user berhasil login?
2. Bagaimana strategi penanganan untuk akun-akun non-aktif (*dormant accounts*) yang tidak pernah login kembali selama lebih dari 2 tahun agar integritas password hash mereka tetap terlindungi dari serangan *offline dictionary attack* jika database bocor?
3. Tentukan parameter tuning Argon2id (`memory_cost`, `time_cost`, `threads`) yang optimal untuk lingkungan web synchronous berbasis PHP-FPM, dan jelaskan *trade-off* performa serta ancaman *CPU/Memory Exhaustion* (Resource Starvation) jika parameter diatur terlalu agresif.

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Trust Secure File Intake and Storage Vault Engine

#### Problem Statement
Sebuah enterprise perbankan memerlukan modul intake file terisolasi (*Zero-Trust Document Vault Engine*) yang menerima dokumen (PDF, PNG, JPG) dari nasabah via API. Sistem ini merupakan sasaran utama serangan webshell, remote code execution (RCE) melalui metadata injection (seperti ImageMagick exploits), SVG script injection, path traversal, dan server storage exhaustion.

#### Requirements
1. **Strict Type and Pipeline Design**: Bangun class service murni PHP 8.2+ (tanpa framework eksternal, gunakan strict typing `declare(strict_types=1);`).
2. **Multi-Stage Validation Pipeline**:
   - Validasi ukuran file dan MIME type berbasis *Magic Bytes* / *File Signatures* secara strictly whitelisted (hanya menerima `image/jpeg`, `image/png`, `application/pdf`).
   - Ekstrak dan bersihkan metadata gambar (stripping EXIF data) untuk memitigasi polyglot shell dan informasi sensitif tanpa memicu kerentanan image parsing memory-unsafe.
   - Sanitasi nama file mutlak: Sistem harus menghasilkan nama file baru menggunakan *Cryptographically Secure Random String* (CSPRNG) dan penanganan ekstensi deterministik. Simpan metadata asli (asli nama file terenkripsi jika diperlukan) terpisah dari sistem berkas.
3. **Storage Isolation**:
   - Lokasi penyimpanan file fisik harus berada di luar *Document Root* web server (non-executable directory).
   - Berikan mekanisme serving file yang aman menggunakan teknik *chunked streaming* dengan header keamanan ketat (`Content-Type` yang dipaksa, `X-Content-Type-Options: nosniff`, `Content-Disposition: attachment; filename=...`, dan *Content Security Policy*).
4. **Defensive Cryptography**: Implementasikan verifikasi integritas hash SHA-256 pada file yang diunggah dan verifikasi *Timing-Attack Safe* saat membaca kembali file berdasarkan token otorisasi.

#### Constraints
- **Zero Shell Executions**: Dilarang menggunakan fungsi sistem `exec()`, `shell_exec()`, `passthru()`, atau `system()`.
- **Memory Consumption Constraint**: Modul harus mampu memproses dokumen PDF hingga 20 MB dengan alokasi memori PHP-FPM maksimal **32 MB per worker** (Gunakan *stream wrappers* atau *buffered chunk processing*, dilarang me-load seluruh file 20 MB ke dalam memori variabel string menggunakan `file_get_contents()`).
- **PHP Native Implementation**: Gunakan modul `ext-fileinfo`, `ext-gd` (hanya untuk image re-encoding/stripping yang aman), `ext-sodium` atau `ext-random`.

#### Expected Output
1. File 1: `Security/Vault/SecureFileUploader.php` (Menangani validasi stream, magic bytes, CSPRNG filename, dan storage non-executable).
2. File 2: `Security/Vault/SecureFileStreamer.php` (Menangani *chunked reading*, *memory-safe download delivery*, dan *security headers*).
3. Unit/Integration Test script singkat atau simulasi eksekusi yang membuktikan bahwa file dengan ekstensi ganda (e.g., `payload.php.jpg`) atau file palsu (e.g., PHP script yang dinamai `malicious.pdf` namun berisi tag `<?php`) ditolak secara absolut dengan *custom domain exception*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mengapa *Prepared Statements* memisahkan instruksi SQL (AST) dari data pada level database driver dan bagaimana setting `PDO::ATTR_EMULATE_PREPARES => false` beroperasi.
- [ ] Perbedaan fundamental antara komputasi cepat (SHA/MD5) dan komputasi memori-intensif (Argon2id, Bcrypt) dalam mitigasi serangan brute-force hardware akselerasi.
- [ ] Mekanisme internal Zend Engine saat memproses serialisasi objek, struktur *POP Chain*, dan bahaya laten fungsi `unserialize()`.
- [ ] Karakteristik *Constant-Time Comparison* pada `hash_equals()` untuk menggagalkan *Side-Channel Timing Attacks*.
- [ ] Keterbatasan validasi regex/filter URL terhadap representasi numerik IP alternatif dan teknik serangan *DNS Rebinding SSRF*.
- [ ] Bahaya transmisi *Stream Wrappers* arbitrary (`phar://`, `php://filter`) dalam fungsi file-system bawaan PHP.
- [ ] Peran header keamanan HTTP pertahanan modern (`Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `SameSite` cookie).

### Saya tidak perlu menghafal:
- [ ] Implementasi algoritma matematika detail internal S-Boxes atau round constants pada AES atau Argon2id.
- [ ] Seluruh daftar kode hex *magic bytes* untuk setiap format file di dunia (cukup memahami cara kerja deteksi signaturnya via `ext-fileinfo` dan *RFC specifications*).
- [ ] Sintaks baris per baris implementasi wrapper cURL di library pihak ketiga (cukup memahami opsi low-level konfigurasi keamanan seperti `CURLOPT_PROTOCOLS`, `CURLOPT_REDIR_PROTOCOLS`, dan socket bindings).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi koneksi database PDO dengan parameter keamanan tingkat enterprise (`PDO::ERRMODE_EXCEPTION`, non-emulated prepares, UTF-8 charset).
- [ ] Mengimplementasikan lifecycle autentikasi modern menggunakan `password_hash()` dan `password_needs_rehash()` dengan algoritma Argon2id.
- [ ] Membangun pipeline intake file yang resisten terhadap polyglot, path traversal, dan zero-day execution tanpa bergantung pada dokumen root web server.
- [ ] Memitigasi serangan *concurrency race condition* menggunakan teknik locking pada transaksi basis data (pessimistic lock) maupun distributed lock (Redis).
- [ ] Melakukan sanitasi kontekstual yang tepat berdasarkan target keluaran data (HTML Body, HTML Attribute, JavaScript Variable, URL Query Parameter, JSON Block).
- [ ] Mengaudit source code PHP untuk mengidentifikasi fungsi-fungsi rentan (sinkhole) seperti `unserialize()`, `eval()`, `extract()`, `$$dynamic_variables`, dan *insecure file inclusions*.