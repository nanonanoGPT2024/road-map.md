# BAB 07: Quiz, Challenge, & Knowledge Check
**Autentikasi, Otorisasi, & Keamanan Identitas**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Diferensiasi Eksplisit AuthN vs AuthZ:**
   Jelaskan perbedaan mendasar antara *Authentication* (Autentikasi/AuthN) dan *Authorization* (Otorisasi/AuthZ) dalam siklus hidup HTTP *request*. Bagaimana Anda memisahkan implementasi keduanya di lapisan middleware aplikasi backend agar tidak terjadi *tight coupling* antara identifikasi subjek dan pengecekan hak akses?
2. **Karakteristik Kriptografi Password Hashing:**
   Mengapa algoritma *cryptographic hash* berkecepatan tinggi seperti SHA-256 atau MD5 dinilai cacat fatal (*insecure*) untuk penyimpanan kata sandi, meskipun ditambahkan *salt* statis? Analisis mengapa algoritma seperti Argon2id atau bcrypt secara arsitektur lebih unggul dalam memitigasi serangan berbasis GPU/ASIC *brute-force* dan *rainbow tables*.
3. **Stateful Session vs Stateless Token (JWT):**
   Bandingkan arsitektur *Stateful Session* (memanfaatkan database/in-memory store seperti Redis) dengan *Stateless Token* (JSON Web Token). Evaluasi trade-off keduanya dalam aspek beban memori server, dependensi I/O jaringan, kompleksitas *horizontal scaling*, serta kemampuannya menangani terminasi sesi instan (*instant session revocation*).
4. **Struktur Kriptografis dan Integritas JSON Web Token (JWT):**
   Bedah tiga komponen utama JWT (`Header`, `Payload`, `Signature`). Jelaskan secara matematis dan konseptual bagaimana penerima (backend) memverifikasi bahwa muatan data (*claims*) di dalam JWT belum dimanipulasi oleh pihak ketiga tanpa perlu melakukan *database lookup*, serta jelaskan bahaya membedah token hanya menggunakan teknik `base64url-decode` tanpa verifikasi tanda tangan kriptografis.
5. **RBAC vs ABAC:**
   Bandingkan model kendali akses *Role-Based Access Control* (RBAC) dan *Attribute-Based Access Control* (ABAC). Berikan satu skenario di mana model RBAC murni mengalami kondisi *role explosion* dan jelaskan bagaimana transisi ke ABAC menyelesaikan batasan tersebut melalui evaluasi atribut kontekstual (*environmental/resource attributes*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Paradoks Token Revocation pada Arsitektur JWT:**
   Karena JWT bersifat *stateless* dan memiliki *expiry time* mandiri, bagaimana mekanisme arsitektur backend yang paling optimal untuk menangani kasus darurat: pemblokiran instan pengguna yang diretas atau implementasi fitur "Logout from All Devices" tanpa mengorbankan performa *statelessness* dari seluruh sistem API?
2. **Analisis Timing Attack pada Verifikasi Kredensial:**
   Perhatikan potongan kode pembanding token berikut:
   ```javascript
   function verifyToken(inputToken, storedToken) {
     return inputToken === storedToken;
   }
   ```
   Jelaskan bagaimana operator `===` (atau fungsi pembanding string standar) menciptakan kerentanan *Side-Channel Timing Attack*. Bagaimana mekanisme internal perbandingan *byte-by-byte* menyebabkan kebocoran informasi durasi eksekusi, dan bagaimana cara memitigasinya menggunakan *constant-time comparison algorithm*?
3. **Refresh Token Rotation (RTR) & Reuse Detection:**
   Jelaskan mekanisme internal *Refresh Token Rotation*. Mengapa backend harus membatalkan *seluruh token family* (semua token yang diturunkan dari sesi awal) jika sebuah *refresh token* yang sudah kedaluwarsa atau sudah pernah dipakai tiba-tiba dikirimkan kembali oleh klien? Jelaskan skenario eksploitasi yang dicegah oleh pola ini.
4. **Client-Side Storage Vulnerability Matrix:**
   Evaluasi risiko keamanan penyimpanan token otentikasi di sisi *client* antara `Web Storage API` (`localStorage`/`sessionStorage`) versus `HttpOnly, Secure, SameSite=Strict/Lax Cookie`. Uraikan bagaimana skenario eksploitasi *Cross-Site Scripting* (XSS) dan *Cross-Site Request Forgery* (CSRF) beroperasi pada masing-masing media penyimpanan tersebut dan mekanisme pertahanan backend yang wajib diimplementasikan.
5. **Eksploitasi "alg: none" dan Algoritma Key-Confusion pada JWT:**
   Jelaskan secara teknis bagaimana kerentanan implementasi JWT dapat dieksploitasi jika parser JWT di backend menerima *header* `{"alg": "none"}` atau ketika terjadi *Asymmetric-to-Symmetric Key Confusion Attack* (backend mengharapkan RSA/ECDSA public key, tetapi penyerang menandatangani token menggunakan HMAC-SHA256 dengan memanfaatkan public key server sebagai *secret*). Bagaimana cara mencegah serangan ini di tingkat konfigurasi kode?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kegagalan Latensi dan Bottleneck Sentralisasi Auth pada 250k RPS
Sebuah platform *e-commerce* mengadopsi arsitektur *microservices* (terdiri dari 40+ domain servis independen). Pada arsitektur saat ini, setiap kali sebuah *incoming request* tiba di API Gateway, API Gateway meneruskannya ke servis hilir (*downstream services*). Setiap *downstream service* melakukan verifikasi hak akses dengan mengeksekusi panggilan gRPC sinkron ke sebuah *Central Identity Service* (Auth Service) yang membaca data sesi dari cluster Redis terpusat.

Menjelang event *Flash Sale*, beban sistem melonjak hingga 250.000 Request Per Second (RPS). Cluster Redis pada Auth Service mengalami utilisasi CPU 100%, terjadi penumpukan koneksi (*connection pool exhaustion*), dan *network latency* antar servis meroket dari 2ms menjadi 1.800ms, memicu kegagalan berantai (*cascading failure*) yang melumpuhkan seluruh platform.

**Pertanyaan Diagnostik & Arsitektur:**
1. Di mana letak kelemahan fatal arsitektur autentikasi/otorisasi ini dalam konteks sistem terdistribusi?
2. Bagaimana Anda merancang ulang arsitektur autentikasi dan otorisasi sistem ini menggunakan kombinasi *Asymmetric JWT Verification* (Public/Private Key) di edge/servis dan pola *Claims-based propagation* agar *downstream services* tidak perlu lagi melakukan panggilan jaringan ke Auth Service untuk setiap request?
3. Bagaimana strategi Anda memvalidasi pencabutan hak akses (*revocation/blacklisting*) pengguna jika menggunakan arsitektur terdistribusi tersebut tanpa kembali membebani *Central Identity Service*?

---

### Skenario B: Race Condition pada Refresh Token Rotation yang Memutus Sesi Valid Pengguna
Sebuah aplikasi web *Single Page Application* (SPA) memuat dashboard analitik kompleks. Ketika pengguna membuka dashboard setelah beberapa hari tidak aktif, aplikasi secara bersamaan memicu 6 *HTTP request* asinkron melalui `Promise.all()` untuk menarik data widget yang berbeda.

Karena *Access Token* telah kedaluwarsa, keenam request tersebut secara simultan menerima respons HTTP `401 Unauthorized`. Klien kemudian mengintersep respons tersebut dan mengeksekusi mekanisme *token refresh* dengan mengirimkan *Refresh Token* yang sama ke endpoint `/api/v1/auth/refresh` secara hampir bersamaan (berselisih 5-15 milidetik).

Sistem autentikasi backend telah menerapkan *Strict Refresh Token Rotation* (RTR). Akibatnya, request pertama berhasil mendapatkan pasangan token baru dan membatalkan *Refresh Token* lama di database. Request kedua hingga keenam yang tiba beberapa milidetik kemudian terdeteksi sebagai "Upaya Penggunaan Ulang Token yang Sudah Kedaluwarsa" (*Token Reuse Detected*). Sistem mengasumsikan telah terjadi pencurian kredensial, sehingga secara otomatis membatalkan seluruh *Token Family* dan mengunci sesi. Pengguna sah tiba-tiba terlempar keluar (*logged out*) ke halaman login dengan pesan kesalahan keamanan.

**Pertanyaan Diagnostik & Arsitektur:**
1. Bedah titik kegagalan (*race condition*) pada penanganan mutasi *Refresh Token* di lapisan database/backend dan logika *client-side interceptor*.
2. Rancang solusi arsitektur backend untuk menangani kondisi konkurensi ini menggunakan teknik *Grace Period* (Window of Tolerance) atau mekanisme *Locking/Debounce*, tanpa melonggarkan proteksi terhadap serangan *Replay Attack* yang sebenarnya.
3. Bagaimana skema optimasi yang wajib diterapkan di lapisan *frontend/client interceptor* untuk mencegah penembakan endpoint refresh berulang kali saat menerima badai respons 401 secara paralel?

---

### Skenario C: Dilema Skalabilitas Multi-Tenant: Transisi RBAC Sederhana ke Fine-Grained Authorization
Perusahaan SaaS B2B Anda berkembang pesat dari melayani ribuan pengguna individual menjadi melayani perusahaan berskala enterprise (*multi-tenant*). Pada awalnya, skema otorisasi menggunakan RBAC sederhana yang disimpan di basis data relasional:
`Users` -> `User_Roles` -> `Roles` (`Admin`, `Editor`, `Viewer`).

Klien enterprise baru mengajukan kebutuhan kepatuhan (*compliance*) yang ketat:
- Manajer cabang Jakarta hanya boleh menyetujui (*Approve*) pengeluaran anggaran (*Expense Report*) jika departemennya adalah "Logistik", nominal di bawah Rp 50.000.000, dan request dibuat pada hari kerja (Senin-Jumat, jam 08:00 - 17:00).
- Auditor eksternal hanya boleh melihat dokumen finansial yang statusnya sudah "Finalized" dan terbatas pada tahun fiskal berjalan.

Tim pengembang Anda mencoba mempertahankan model RBAC dengan membuat *role* baru seperti `Admin_Jakarta_Logistik_Under50M`, `Auditor_CurrentFiscalYear`, dan seterusnya. Dalam hitungan minggu, tabel `Roles` membengkak menjadi ratusan entri yang tidak terkendali (*Role Explosion*), menyebabkan logika kondisional di kode backend (`if/else`) menjadi sangat rumit, rawan bug keamanan (*privilege escalation*), dan memperlambat latensi p99 database karena operasi *JOIN* yang masif.

**Pertanyaan Diagnostik & Arsitektur:**
1. Mengapa pola RBAC konvensional gagal total menyelesaikan kebutuhan ini, dan apa saja dampak jangka panjang terhadap *maintainability* dan *security audit* jika tim tetap memaksakan pola tersebut?
2. Bagaimana Anda merancang transisi arsitektur kendali akses dari RBAC ke model *Attribute-Based Access Control* (ABAC) atau *Policy-Based Access Control* (PBAC) (misalnya menggunakan engine seperti Open Policy Agent / Casbin / AWS Cedar)? Tentukan komponen *Policy Enforcement Point* (PEP) dan *Policy Decision Point* (PDP) dalam arsitektur Anda.
3. Rancang struktur model data atau deklarasi *policy* (dalam format pseudo-code/JSON) yang merepresentasikan aturan otorisasi manajer cabang di atas, serta jelaskan bagaimana sistem mengevaluasi request tersebut dengan latensi sub-10ms.

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Engine Autentikasi Produksi yang Resilien, Aman dari Race Condition, dan Zero-Trust Ready

#### Problem Statement
Anda diminta untuk membangun pondasi modul autentikasi dan manajemen identitas inti (*core identity engine*) untuk sistem backend finansial. Modul ini harus mampu menangani siklus hidup kredensial secara aman, resisten terhadap kebocoran data (*data breaches*), kebal terhadap serangan konkurensi (seperti pada Skenario B), dan menyediakan mekanisme jejak audit (*auditability*) yang ketat.

#### Functional Requirements
1. **Pendaftaran & Penyimpanan Kredensial:**
   - Endpoint pendaftaran (`POST /api/v1/auth/register`) yang memvalidasi kekuatan kata sandi secara deterministik (entropi, panjang minimal, pencegahan penggunaan kata sandi pasaran).
   - Penyimpanan password wajib diproteksi menggunakan **Argon2id** (konfigurasikan *memory cost*, *time cost*, dan *parallelism* sesuai standar OWASP terkini) atau **bcrypt** (cost factor minimal 12).
2. **Autentikasi & Issuance Token:**
   - Endpoint login (`POST /api/v1/auth/login`) yang menghasilkan pasangan:
     - **Access Token:** Asymmetric signed JWT (menggunakan RS256 atau EdDSA/Ed25519) dengan masa hidup pendek (*Short-lived*, maks 15 menit). Payload harus seminimal mungkin (Subject ID, Tenant ID, Roles/Permissions).
     - **Refresh Token:** Cryptographically secure pseudo-random string (min 256-bit entropy) yang disimpan dalam database sebagai nilai *hash* (SHA-256), bukan *plaintext*. Masa hidup 7 hari.
   - Refresh token dikirimkan kembali ke klien melalui *cookie* dengan atribut: `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth/refresh`.
3. **Rotasi Token Resilien dengan Grace Period:**
   - Endpoint perpanjangan (`POST /api/v1/auth/refresh`).
   - Menerapkan *Refresh Token Rotation* (RTR): setiap kali refresh token digunakan, sistem membatalkannya dan menerbitkan refresh token yang baru.
   - **Mekanisme Grace Period Konkuren:** Jika sistem menerima request refresh dengan token yang *baru saja dirotasi* dalam jendela toleransi maksimal **10 detik** (untuk mengantisipasi *parallel network requests* dari SPA/klien), backend **tidak boleh** membatalkan sesi, melainkan harus mengembalikan pasangan token yang sama yang diterbitkan pada rotasi terakhir.
   - **Pencegahan Replay:** Jika token yang sama digunakan *setelah* jendela toleransi 10 detik berakhir, sistem **wajib** mendeteksi ini sebagai intrusi, seketika membatalkan semua token yang berada dalam *Family ID* yang sama, dan mencatat event audit keamanan tingkat tinggi.
4. **Logout & Invalidasi:**
   - Endpoint logout (`POST /api/v1/auth/logout`) yang menghapus cookie, memvalidasi sesi, dan mengubah status *Refresh Token Family* menjadi *revoked* di database.
5. **Endpoint Terproteksi (Resource Server):**
   - Middleware otentikasi yang memverifikasi tanda tangan JWT publik (menggunakan *Public Key* / JWKS) pada rute terproteksi (`GET /api/v1/accounts/me`). Verifikasi wajib dilakukan secara *stateless* tanpa menyentuh database.

#### Technical Constraints & Anti-Patterns
- **Dilarang:** Menyimpan refresh token dalam format *plaintext* di database.
- **Dilarang:** Menyimpan data sensitif (password hash, NIK, nomor kartu kredit) di dalam payload JWT.
- **Dilarang:** Menggunakan pembanding string standar (`==` atau `===`) untuk memverifikasi secret atau token; wajib menggunakan *constant-time comparison* (`crypto.timingSafeEqual`).
- **Dilarang:** Mengizinkan algoritma `none` pada JWT verification library.

#### Expected Deliverables
1. **Source Code Implementation:** Implementasi backend fungsional (menggunakan Node.js/Go/Java/Python/Rust).
2. **Database Schema:** Skema relasional atau document store untuk tabel `users`, `refresh_tokens`, dan `audit_logs` (lengkap dengan indeks yang tepat).
3. **Automated Concurrency Test Suite:** Sebuah skrip pengujian otomatis (integrasi/e2e) yang mendemonstrasikan:
   - Skenario normal: Registrasi -> Login -> Akses Endpoint -> Refresh -> Logout.
   - Skenario *Race Condition*: Pengiriman 5 panggilan `POST /refresh` secara paralel (bersamaan dalam rentang < 2 detik), membuktikan bahwa sistem tidak memblokir pengguna sah dan berhasil mengembalikan token yang valid.
   - Skenario *Breach Simulation*: Pengiriman ulang token lama setelah rentang > 10 detik, membuktikan sistem memicu alarm *Token Reuse Detected* dan membatalkan seluruh sesi dalam family tersebut.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda sebelum melangkah ke domain arsitektur backend berikutnya.

### Saya harus memahami:
- [ ] Perbedaan matematis dan konseptual antara algoritma enkripsi (simetris/asimetris), hashing satu arah (SHA), dan password derivation functions (Argon2id, bcrypt, PBKDF2).
- [ ] Batasan arsitektur JWT stateless dan mengapa JWT tidak dirancang secara alami untuk fitur pembatalan sesi instan (*instant revocation*).
- [ ] Mengapa *public key cryptography* (RS256, ES256, Ed25519) lebih diutamakan dalam arsitektur microservices dibanding *symmetric secret* (HS256) untuk verifikasi JWT.
- [ ] Bagaimana vektor serangan *Side-Channel Timing Attack* dapat mengekspos rahasia sistem melalui analisis variasi waktu CPU, dan formula matematis di balik algoritma *constant-time*.
- [ ] Perbedaan vektor ancaman antara XSS dan CSRF serta implementasi lapisan pertahanan berlapis (CSP, SameSite cookies, CSRF tokens, sanitasi input).
- [ ] Mengapa *Role Explosion* terjadi pada RBAC skala besar dan kapan waktu yang tepat untuk bertransisi ke ABAC, ReBAC, atau PBAC.

### Saya tidak perlu menghafal:
- [ ] Rumus matematika internal primitif kriptografi (seperti permutasi bit S-box pada AES atau komputasi kurva eliptis secara manual). Anda hanya perlu memahami sifat matematisnya (*computational hardness*, *collision resistance*).
- [ ] Setiap spesifikasi RFC lengkap dari OAuth 2.0 (RFC 6749) dan OpenID Connect di luar kepala. Anda hanya perlu memahami *Grant Types*, alur pertukaran kredensial (*authorization code exchange*), dan model ancaman utamanya.
- [ ] Spesifikasi byte format ASN.1/DER dari sertifikat kunci publik (PEM). Gunakan library standar kriptografi bahasa pemrograman Anda.

### Saya harus bisa melakukan:
- [ ] Menghitung dan mengonfigurasi parameter *cost* pada Argon2id/bcrypt berdasarkan latensi target server (misal: ~250-500ms hashing time per login attempt pada core server produksi).
- [ ] Menulis middleware verifikasi JWT custom yang menangani validasi *signature*, *issuer*, *audience*, dan *expiration* secara aman serta kebal terhadap *algorithm-switching attack*.
- [ ] Merancang skema basis data relasional yang dinormalisasi untuk menangani siklus hidup *Refresh Token Rotation* dengan konsep *Token Families* dan status audit integritas.
- [ ] Mengimplementasikan *constant-time comparison* untuk setiap operasi verifikasi token statis, API keys, atau hash signature.
- [ ] Menulis unit test dan integration test yang secara eksplisit mereproduksi dan menguji *race condition* pada endpoint autentikasi menggunakan panggilan konkuren multi-thread atau *event loop asynchronous*.
- [ ] Mengonfigurasi atribut HTTP Cookie (`HttpOnly`, `Secure`, `SameSite`, `Domain`, `Path`) secara presisi untuk membatasi vektor kebocoran token pada arsitektur decoupled (SPA dan API terpisah).