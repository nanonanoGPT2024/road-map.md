# Modul 01: Web Application & API Security

---

## 1. Identitas Modul

* **Track:** Cyber Security Engineering & Application Defense
* **Kategori:** 07-Quality-and-Security
* **Bab:** 05 – Web Application & API Security
* **Tingkat Kesulitan:** Advanced / Lanjutan
* **Prasyarat:** 
  * Pemahaman mendalam protokol HTTP/1.1 & HTTP/2 (Header, Method, Statelessness, TLS/mTLS)
  * Kemahiran pemrograman backend (Node.js/TypeScript, Python, atau Go)
  * Pemahaman dasar arsitektur basis data relasional (SQL) dan dokumen (NoSQL)
  * Konsep dasar kriptografi simetris/asimetris (HMAC, RSA, ECDSA) dan CI/CD pipeline
* **Estimasi Waktu Penyelesaian:** 16 Jam Pembelajaran Efektif (Teori, Bedah Kode, dan Lab Hands-on)

---

## 2. Learning Objectives (LO)

Setelah menyelesaikan modul ini, peserta ajar memiliki kompetensi terukur:

* **LO-01:** Menganalisis dan merekonstruksi kelemahan injeksi struktural (SQL Injection, Cross-Site Scripting) serta mengeksekusi mitigasi berbasis *context-aware encoding* dan *parameterized abstraction*.
* **LO-02:** Mengisolasi vektor serangan SSRF (*Server-Side Request Forgery*) pada arsitektur hybrid cloud dengan merancang segmentasi *egress traffic* dan validasi DNS/IP berbasis *denylist/allowlist*.
* **LO-03:** Mendiagnosis kerentanan otorisasi granular (IDOR dan BOLA) pada arsitektur microservices dan API modern melalui implementasi *Object-Level Access Control* (OLAC) dan *Attribute-Based Access Control* (ABAC).
* **LO-04:** Mengidentifikasi dan memitigasi *Complex Business Logic Flaws* (race condition, workflow bypass, integrity manipulation) menggunakan *atomic transactions*, distributed locking, dan finite state machines (FSM).
* **LO-05:** Menerapkan pengamanan menyeluruh pada antarmuka REST/GraphQL terhadap serangan *Mass Assignment* dan *Broken Object Property Level Authorization* menggunakan DTO validation dan immutable data structures.
* **LO-06:** Mengevaluasi integritas token autentikasi (JWT) dan alur delegasi (OAuth2 / OIDC) untuk memblokir serangan manipulasi algoritma, *token sidejacking*, dan *redirect URI poisoning*.
* **LO-07:** Merancang integrasi pipeline DevSecOps otomatis menggunakan perkakas SAST (*Static Application Security Testing*), DAST (*Dynamic Application Security Testing*), dan SCA (*Software Composition Analysis*).
* **LO-08:** Menyusun matriks remediasi terstruktur sesuai standar NIST SP 800-53, OWASP ASVS (*Application Security Verification Standard*) Level 3, dan MITRE ATT&CK.

---

## 3. Concept Map & Architecture Diagram

```
+-------------------------------------------------------------------------------------------------------+
|                                        EDGE & CLIENT PERIMETER                                        |
|  [ User Browser / Mobile App ] <----> [ WAF / Cloudflare / CDN ] <----> [ API Gateway (Kong/Envoy) ]   |
|                                                                                |                      |
|                               +------------------------------------------------+                      |
|                               | Inspection: TLS Termination, Rate Limit, WAF Signature, OIDC Introspection
v                               v                                                                       |
+-------------------------------------------------------------------------------------------------------+
|                                    INTERNAL APPLICATION ECOSYSTEM                                     |
|                                                                                                       |
|  +------------------------+      Context Prop.      +--------------------------+                      |
|  |   Frontend / BFF Node  | ----------------------> |   Backend Core Service   |                      |
|  | (CSRF, XSS Mitigation) |   (Signed JWT Claims)   | (BOLA/IDOR Enforcement)  |                      |
|  +------------------------+                         +--------------------------+                      |
|              |                                                    |                                   |
|              v                                                    v                                   |
|  +------------------------+                         +--------------------------+                      |
|  | Third-Party Webhook    |                         | Data Layer (DB/ORM)      |                      |
|  | (SSRF Guard & Allowlist)|                         | (Parameterized Queries)  |                      |
|  +------------------------+                         +--------------------------+                      |
+-------------------------------------------------------------------------------------------------------+
|                                     CONTINUOUS ASSURANCE PIPELINE                                     |
|                                                                                                       |
|  [ Git Push ] --> [ SCA: Dependency Vulnerabilities ] --> [ SAST: Taint Analysis ]                    |
|                          |                                        |                                   |
|                          v                                        v                                   |
|               [ Container Image Sign ] ---------> [ DAST & Dynamic Policy (Staging) ]                  |
+-------------------------------------------------------------------------------------------------------+
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Lanskap arsitektur perangkat lunak telah bergeser secara fundamental dari monolitik terisolasi menuju sistem terdistribusi, API-first, dan ekosistem multi-cloud. Perubahan paradigma ini membawa konsekuensi signifikan terhadap postur keamanan:

1. **Evolusi Attack Surface:** API publik mengekspos model data internal secara langsung. Kesalahan konfigurasi otorisasi dapat membuka akses eksfiltrasi data secara masif tanpa memicu peringatan WAF konvensional.
2. **Dampak Finansial dan Kepatuhan:** Kebocoran data akibat kerentanan seperti IDOR atau SQLi melanggar regulasi global (GDPR, HIPAA, PCI-DSS v4.0, UU PDP Indonesia). Denda administratif dan sanksi operasional dapat melumpuhkan kelangsungan bisnis.
3. **Kegagalan Paradigma "Perimeter Defense":** Kehadiran mikroservis dan containerization menuntut model *Zero Trust Architecture*. Mempercayai lalu lintas data internal secara implisit membuka ruang eksploitasi pergerakan lateral (*lateral movement*) via SSRF.
4. **Pergeseran Keamanan ke Hulu (Shift-Left):** Biaya remediasi cacat arsitektur keamanan di fase produksi mencapai 30 hingga 100 kali lebih mahal dibandingkan penanganan di fase *design* dan *implementation*. Mengotomatiskan inspeksi SAST/DAST/SCA di pipeline CI/CD bukan lagi opsional, melainkan kebutuhan operasional inti.

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### Modern OWASP Top 10
* **SQL Injection (SQLi):** Kerentanan di mana input yang tidak terpercaya disisipkan ke dalam interpreter SQL tanpa isolasi struktur sintaksis, memungkinkan eksekutor query memanipulasi logika pernyataan basis data.
* **Cross-Site Scripting (XSS):** Kondisi saat aplikasi web menyertakan data yang tidak tervalidasi atau tidak tersanitasi ke dalam keluaran web yang dikirim ke browser pengguna, memicu eksekusi skrip berbahaya dalam konteks sesi korban.
* **Server-Side Request Forgery (SSRF):** Cacat keamanan yang memungkinkan penyerang memaksa aplikasi sisi server melakukan permintaan HTTP/jaringan ke lokasi yang tidak diinginkan, umumnya menyasar jaringan internal, antarmuka *loopback*, atau layanan metadata cloud (169.254.169.254).
* **Insecure Direct Object References (IDOR):** Sub-kategori dari kegagalan kontrol akses (*Broken Access Control*), terjadi ketika aplikasi menggunakan identitas masukan pengguna untuk mengakses objek basis data secara langsung tanpa memvalidasi otorisasi kepemilikan.

### API Security (OWASP Top 10 API Security)
* **Broken Object Level Authorization (BOLA):** Kerentanan nomor satu pada API modern, di mana *endpoint* mengekspos identifier resource tanpa memverifikasi apakah subjek pemanggil memiliki hak akses sah terhadap resource tersebut.
* **Broken Authentication:** Cacat mekanisme identifikasi dan proteksi kredensial, mencakup penanganan sesi yang lemah, ketiadaan perlindungan *brute-force*, dan implementasi tokenisasi yang cacat.
* **Mass Assignment:** Pengikatan payload masukan klien secara otomatis ke variabel internal atau atribut model objek bisnis tanpa filtrasi properti (*strict schema binding*).

### OAuth 2.0, OpenID Connect (OIDC) & JSON Web Tokens (JWT)
* **OAuth 2.0:** Framework otorisasi berbasis token delegasi yang memungkinkan aplikasi pihak ketiga mengakses sumber daya HTTP atas nama pemilik sumber daya.
* **OpenID Connect (OIDC):** Lapisan identitas yang berjalan di atas protokol OAuth 2.0 untuk memvalidasi identitas pengguna akhir dan mengambil klaim profil dasar melalui token identitas (`id_token`).
* **JSON Web Token (JWT):** Standar terbuka (RFC 7519) ringkas dan mandiri (*self-contained*) untuk mentransmisikan informasi antar-pihak secara aman dalam bentuk objek JSON bertanda tangan digital (*signed*).

### DevSecOps Automation
* **Static Application Security Testing (SAST):** Analisis kode sumber (*white-box*) tanpa mengeksekusi program untuk mendeteksi *taint flow*, cacat logika, dan ketidaksesuaian standar keamanan.
* **Dynamic Application Security Testing (DAST):** Evaluasi keamanan aplikasi dari luar (*black-box*) saat aplikasi beroperasi, mensimulasikan vektor serangan melalui antarmuka HTTP publik.
* **Software Composition Analysis (SCA):** Audit otomatis dependensi pihak ketiga dan paket pustaka terbuka untuk mengidentifikasi kerentanan yang terdaftar (CVE) dan pelanggaran lisensi.

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### Mekanisme SQLi vs. Parameterized Queries
Pada SQLi berbasis teks konvensional, interpreter SQL menyatukan representasi string kode program dan data dalam satu buffer sintaksis:
$$\text{Query Buffer} = \text{SQL Command} + \text{Tainted Input}$$
Ketika penyerang memasukkan metadata delimiter (misalnya karakter petik tunggal `'`), struktur pohon sintaksis (*Abstract Syntax Tree* - AST) basis data terdistorsi. 

Sebaliknya, pada *Parameterized Query* (Prepared Statement):
1. Basis data mengompilasi template SQL terlebih dahulu membentuk AST definitif.
2. Parameter data dikirim secara terpisah melalui protokol biner basis data.
3. Basis data memperlakukan parameter murni sebagai nilai literal (tipe data teks, integer, blob), bukan kode eksekusi, sehingga manipulasi struktur sintaksis menjadi mustahil secara matematis.

```
Parameterized Execution Flow:
[ Application ] -- (1) PREPARE "SELECT * FROM users WHERE id = ?" --> [ DB Engine: Compiles AST ]
[ Application ] -- (2) EXECUTE with parameter: ["1 OR 1=1"] ---------> [ DB Engine: Treats input strictly as string ]
```

### Mekanisme SSRF dan Akses Metadata Cloud
Pada lingkungan cloud (AWS, GCP, Azure), instans komputasi mengakses *Instance Metadata Service* (IMDS) melalui alamat IP tautan lokal (*link-local*) `169.254.169.254`. Jika sebuah aplikasi backend menerima URL eksternal (misalnya fitur *fetch image by URL*) tanpa validasi ketat:
1. Penyerang mengarahkan URL masukan ke `http://169.254.169.254/latest/meta-data/iam/security-credentials/`.
2. Backend menerima request dan membuat panggilan HTTP baru dari antarmuka jaringannya sendiri.
3. Node komputasi meloloskan permintaan ke IMDS karena berasal dari internal host.
4. Token kredensial sementara IAM terekspos kembali ke penyerang melalui response body atau timing channel.

Mitigasi berbasis IMDSv2 menggunakan model *session-oriented*:
* Memerlukan *token request* via HTTP `PUT` dengan header custom (`X-aws-ec2-metadata-token-ttl-seconds`).
* Memblokir request yang menyertakan header `X-Forwarded-For` untuk menangkal proxy hopping SSRF.

### Siklus Autentikasi dan Validasi Token JWT
Struktur JWT terdiri dari 3 segmen terpisah oleh titik: `Header.Payload.Signature`.
* Header: Menentukan tipe token dan algoritma penandatanganan (misalnya: `{"alg": "RS256", "typ": "JWT"}`).
* Payload: Berisi data klaim terdaftar, publik, dan privat (misalnya: `sub`, `iss`, `exp`, `role`).
* Signature: Dihasilkan melalui fungsi kriptografi:
$$\text{Signature} = \text{Sign}_{K_{\text{private}}}(\text{Base64Url}(\text{Header}) + "." + \text{Base64Url}(\text{Payload}))$$

Verifikasi sisi server backend:
1. Mengurai header dan payload.
2. Mengambil kunci publik (*Public Key*) dari penyedia identitas (Jwks endpoint).
3. Menghitung validasi tanda tangan secara independen.
4. Memvalidasi batasan masa berlaku (`exp`), waktu aktif (`nbf`), penerbit (`iss`), dan audiens (`aud`).

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

| Kategori / Dimensi | SAST (Static Testing) | DAST (Dynamic Testing) | SCA (Composition Analysis) | IAST (Interactive Testing) |
| :--- | :--- | :--- | :--- | :--- |
| **Konteks Analisis** | *White-box* (Kode sumber, AST, Taint Graph) | *Black-box* (HTTP boundary, runtime response) | Manifest dependensi & lockfiles (`npm`, `pip`, `mvn`) | *Gray-box* (Instrumentasi agen runtime aplikasi) |
| **Fase CI/CD** | Commit, Pull Request, Build | Staging, Pre-production environment | Commit, Build, Release Gate | QA Integration Testing, Staging |
| **Tingkat False Positive**| Relatif Tinggi (Membutuhkan *tuning rules*) | Rendah (Menemukan kerentanan terbukti terekspos) | Sangat Rendah (Kecocokan CVE definitif) | Rendah (Konteks runtime memvalidasi eksekusi) |
| **Cakupan Kerentanan** | Cacat sintaks, hardcoded secret, pola logic insecure | Cacat konfigurasi server, runtime headers, sanitasi I/O | Outdated packages, transitive dependencies CVE | Deep logic flow, data leakage antar API boundary |
| **Keterbatasan Utama**| Butuh akses source code; butuh tuning per bahasa | Tidak bisa mendeteksi 100% path kode yang tidak terpanggil | Tidak mendeteksi kerentanan pada kode yang ditulis sendiri | Memerlukan overhead memori dan CPU agen di runtime |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

```
+---------------------------------------------------------------------------------------------------------------+
| VEKTOR SERANGAN        | AKTOR PENYERANG  | TITIK MASUK (ENTRY POINT)    | DAMPAK SISTEMIK                    |
+------------------------+------------------+------------------------------+------------------------------------+
| SQLi (Blind / Time)    | Eksternal        | Query Params, Headers, Body  | Manipulasi DB, Pengambilan Secret  |
| Stored XSS             | Klien Terafiliasi| Form Profil, Webhook Parser  | Pembajakan Akun (Session Hijacking)|
| Cloud SSRF             | Unauthenticated  | Image Import, Webhook URL    | Kompromi Kredensial IAM Metadata   |
| BOLA / IDOR            | Authenticated    | Path Variable `/api/v1/u/{id}`| Pelanggaran Privasi Horizontal/Vert|
| Mass Assignment        | Authenticated    | JSON Body: POST/PUT/PATCH    | Eskalasi Hak Akses (Role: Admin)   |
| JWT Algorithm Swap     | Eksternal        | Header `alg: none` atau HS256| Bypassing Otorisasi Universal      |
| Race Condition (Logic) | Authenticated    | Endpoint Pembayaran/Voucher  | Transaksi Ganda Tanpa Saldo Cukup  |
+---------------------------------------------------------------------------------------------------------------+
```

---

## 9. Code Example Sederhana (Minimal & Clear)

### Kasus: Mitigasi SQL Injection pada Go (Golang)

#### Rentan (Vulnerable Anti-Pattern)
Penggabungan string dinamis membatalkan analisis semantik compiler basis data:

```go
package main

import (
	"database/sql"
	"fmt"
	"net/http"
)

func insecureUserHandler(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("id")
	// CACAT: Penggabungan string mentah mengekspos interpreter SQL
	query := fmt.Sprintf("SELECT username, email FROM users WHERE id = '%s'", userID)
	
	row := db.QueryRow(query)
	var username, email string
	if err := row.Scan(&username, &email); err != nil {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}
	fmt.Fprintf(w, "User: %s, Email: %s", username, email)
}
```

#### Aman (Remediated Pattern)
Menggunakan *parameter substitution* melalui antarmuka driver database:

```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
	"time"
)

func secureUserHandler(db *sql.DB, w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("id")

	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()

	// SECURE: Menggunakan parameter binding (?)
	query := `SELECT username, email FROM users WHERE id = $1`
	
	var username, email string
	err := db.QueryRowContext(ctx, query, userID).Scan(&username, &email)
	if err != nil {
		if err == sql.ErrNoRows {
			http.Error(w, "Resource not found", http.StatusNotFound)
			return
		}
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	fmt.Fprintf(w, "User: %s, Email: %s", username, email)
}
```

---

## 10. Code Example Lanjutan (Production-ready / Hardening / Exploit Analysis)

### Kasus: Hardening SSRF Defense Engine pada Node.js/TypeScript
Implementasi *production-ready* wrapper HTTP client dengan validasi DNS asynchronous, pemblokiran alamat *private/loopback/link-local*, dan pencegahan *DNS Rebinding*.

```typescript
import axios, { AxiosResponse } from 'axios';
import * as dns from 'dns/promises';
import * as ipaddr from 'ipaddr.js';
import { URL } from 'url';

export class SecureHttpClient {
  private static readonly DISALLOWED_RANGES = [
    'unspecified',
    'broadcast',
    'linkLocal',
    'loopback',
    'private',
    'carrierGradeNat'
  ];

  /**
   * Melakukan validasi keamanan alamat IP terhadap SSRF
   * @param ipString Alamat IP v4 atau v6 hasil resolusi DNS
   */
  private static isIpAllowed(ipString: string): boolean {
    try {
      const addr = ipaddr.parse(ipString);
      const range = addr.range();
      
      // Blokir rentang IP internal / privat
      if (this.DISALLOWED_RANGES.includes(range)) {
        return false;
      }

      // Deteksi IPv4-mapped IPv6 addresses (misal: ::ffff:169.254.169.254)
      if (addr.kind() === 'ipv6' && (addr as ipaddr.IPv6).isIPv4MappedAddress()) {
        const mappedV4 = (addr as ipaddr.IPv6).toIPv4Address();
        if (this.DISALLOWED_RANGES.includes(mappedV4.range())) {
          return false;
        }
      }

      return true;
    } catch {
      return false;
    }
  }

  /**
   * Eksekusi aman fetch data URL eksternal dengan mitigasi DNS Rebinding
   */
  public static async safeGet(targetUrl: string): Promise<AxiosResponse<any>> {
    const parsedUrl = new URL(targetUrl);

    if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
      throw new Error(`Skema protokol tidak diizinkan: ${parsedUrl.protocol}`);
    }

    // Resolusi DNS eksplisit sebelum melakukan outbound connection
    const addresses = await dns.lookup(parsedUrl.hostname, { all: true });
    if (!addresses || addresses.length === 0) {
      throw new Error('Gagal meresolusi hostname target');
    }

    // Validasi seluruh IP yang dikembalikan oleh DNS provider
    for (const record of addresses) {
      if (!this.isIpAllowed(record.address)) {
        throw new SecurityException(
          `Akses jaringan ilegal ditolak: ${parsedUrl.hostname} merujuk ke ${record.address}`
        );
      }
    }

    // Gunakan konfigurasi timeout ketat dan tolak auto-redirect untuk mencegah open-redirect hopping
    return await axios.get(targetUrl, {
      timeout: 4000,
      maxRedirects: 0,
      validateStatus: (status) => status >= 200 && status < 300,
      headers: {
        'User-Agent': 'Enterprise-Hardened-Fetcher/2.0',
        'Accept': 'application/json, text/plain'
      }
    });
  }
}

export class SecurityException extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SecurityException';
  }
}
```

---

## 11. Diagram Alur Serangan & Mitigasi (ASCII Art)

### Serangan BOLA / IDOR vs. Mitigasi Berbasis Konteks Objek (OLAC)

```
SKENARIO SERANGAN (UNPROTECTED):
Attacker (User_B, Token_B)            API Gateway                    Order Microservice             Database
       |                                   |                                  |                        |
       |--- GET /api/v1/orders/1094 ------>|                                  |                        |
       |    Header: Bearer Token_B         |--- Forward to Service ---------->|                        |
       |                                   |                                  |--- SELECT * FROM orders|
       |                                   |                                  |    WHERE id = 1094 --->|
       |                                   |                                  |<-- Returns Order 1094 -|
       |                                   |                                  |    (Belongs to User_A) |
       |                                   |<-- Return Order 1094 Payload ----|                        |
       |<-- Data User_A Terekspos ---------|                                  |                        |
            (IDOR BERHASIL)

SKENARIO MITIGASI (OBJECT-LEVEL AUTHORIZATION ENFORCED):
Attacker (User_B, Token_B)            API Gateway                    Order Microservice             Database
       |                                   |                                  |                        |
       |--- GET /api/v1/orders/1094 ------>|                                  |                        |
       |    Header: Bearer Token_B         |--- Parse Claims: User_B -------->|                        |
       |                                   |                                  |--- SELECT * FROM orders|
       |                                   |                                  |    WHERE id = 1094     |
       |                                   |                                  |    AND user_id = 'B' ->|
       |                                   |                                  |<-- Returns Empty Set --|
       |                                   |                                  |                        |
       |                                   |<-- 404 Not Found / 403 Forbidden-|                        |
       |<-- HTTP 404 Not Found ------------|                                  |                        |
            (AKSES DITOLAK SECARA DEFENSIVE)
```

---

## 12. Trade-offs & Security vs Usability / Performance

* **Validasi DNS Pra-Permintaan (SSRF Protection) vs. Latensi Jaringan:**
  * *Trade-off:* Menjalankan inspeksi resolusi DNS manual sebelum setiap *outbound request* menambah *overhead* waktu respons sebesar 20-150ms.
  * *Solusi Arsitektural:* Implementasikan *caching resolver* lokal internal (misalnya Unbound atau CoreDNS) dengan TTL pendek (10-30 detik) untuk menjaga reliabilitas verifikasi tanpa mendegradasi throughput I/O secara ekstrem.
* **Token Stateless (JWT) vs. Revokasi Instan:**
  * *Trade-off:* JWT murni berbasis asimetris tidak dapat dicabut (*stateless revocation*) secara instan sebelum masa kedaluwarsa (`exp`) berakhir, tanpa memelihara status di sisi server.
  * *Solusi Arsitektural:* Pasangkan *access token* berumur pendek (misalnya: 5-15 menit) dengan mekanisme *refresh token rotation* yang disimpan di memori tersentralisasi (Redis cluster) untuk menjaga sifat desentralisasi verifikasi API dengan kontrol pemutusan sesi terukur.
* **Content Security Policy (CSP) Ketat vs. Kompatibilitas Framework:**
  * *Trade-off:* Penerapan CSP tanpa `unsafe-inline` atau `unsafe-eval` mencegah eksekusi payload XSS, tetapi dapat menghentikan fungsi pustaka JavaScript lama atau modul analitik pihak ketiga.
  * *Solusi Arsitektural:* Gunakan *Cryptographic Nonce-based CSP* (`strict-dynamic`) yang diinjeksi secara unik per-request oleh reverse proxy untuk mengizinkan skrip resmi.

---

## 13. Edge Cases & Complex Failure Modes

1. **DNS Rebinding pada Proteksi SSRF:**
   * *Mekanisme:* Penyerang mendaftarkan domain (misal: `rebind.attacker.com`) dengan konfigurasi server DNS kustom. Pada permintaan pertama, DNS mengembalikan IP publik valid (melewati validasi awal). Tepat ketika *HTTP client library* melakukan koneksi TCP aktual milidetik berikutnya, DNS mengembalikan alamat internal `127.0.0.1` atau `169.254.169.254`.
   * *Penanganan:* Kunci koneksi TCP socket langsung ke alamat IP yang telah divalidasi, dengan menyematkan resolusi IP secara statis pada transport layer HTTP client, bukan mengizinkan socket layer melakukan re-resolution otomatis.
2. **Kelemahan JWT Key Confusion Attack (RS256 ke HS256):**
   * *Mekanisme:* Jika backend memverifikasi token menggunakan pustaka yang mengekstraksi algoritma langsung dari header JWT tanpa validasi eksplisit, penyerang dapat mengubah header menjadi `{"alg": "HS256"}` dan menandatangani token menggunakan *Public Key* RSA server (yang bersifat publik dan dapat diakses bebas) sebagai shared secret HMAC.
   * *Penanganan:* Server penegak otorisasi wajib mendeklarasikan secara statis algoritma yang diterima (misal: `algorithms: ['RS256']`), dan secara mutlak menolak penggunaan algoritma berbasis simetris jika kunci verifikasi bertipe asimetris.
3. **Race Condition pada Validasi Saldo (Limit Overrun):**
   * *Mekanisme:* Dua permintaan HTTP concurrent dikirim secara bersamaan pada waktu $T_0$. Keduanya membaca saldo $100. Keduanya lolos validasi `if (balance >= 100)`. Keduanya mengeksekusi penarikan, menghasilkan saldo akhir negatif $-100$.
   * *Penanganan:* Terapkan *Pessimistic Locking* di tingkat basis data (`SELECT ... FOR UPDATE`), atau gunakan transaksi atomik berkondisi:
     ```sql
     UPDATE accounts SET balance = balance - 100 WHERE id = $1 AND balance >= 100;
     ```

---

## 14. Anti-Patterns & Common Vulnerabilities

* **Anti-Pattern 1: Hidden Form Field Authorization**
  * *Deskripsi:* Mengandalkan atribut tersembunyi pada frontend seperti `<input type="hidden" name="role" value="user">` atau mengasumsikan parameter client-side tidak dapat diubah oleh pengguna.
  * *Koreksi:* Status identitas dan peran (*role*) mutlak ditentukan melalui konteks token terverifikasi di server backend.
* **Anti-Pattern 2: Permissive CORS Configuration**
  * *Deskripsi:* Mengembalikan header `Access-Control-Allow-Origin: *` bersamaan dengan `Access-Control-Allow-Credentials: true`.
  * *Koreksi:* Validasi origin terhadap daftar domain tepercaya secara ketat; jangan pernah merefleksikan nilai header `Origin` request secara membabi buta ke dalam response CORS.
* **Anti-Pattern 3: Regex DOS (ReDoS) pada Validasi Masukan**
  * *Deskripsi:* Menggunakan ekspresi reguler yang rentan mengalami *catastrophic backtracking* (misal: `^(a+)+$`) untuk memvalidasi masukan panjang.
  * *Koreksi:* Terapkan batas panjang string (*string length clamping*) sebelum evaluasi Regex, dan gunakan mesin Regex beralgoritma linear seperti Google RE2.

---

## 15. Best Practices & Enterprise Remediation Guide

1. **Context-Aware Sanitization & Parameterization:**
   * Gunakan template engine yang menerapkan *context-aware output encoding* otomatis (seperti Go `html/template`).
   * Wajibkan penggunaan ORM/Query Builder berparameter (Prisma, Hibernate, SQLAlchemy) dan larang penggunaan raw SQL concatenation melalui linter rules (*eslint-plugin-security*, *semgrep*).
2. **Defensive API Gateways & Zero Trust Networking:**
   * Terapkan skema OpenAPI v3 strict validation pada API Gateway (tolak payload yang mengandung properti tak terdaftar guna mengeliminasi *Mass Assignment*).
   * Gunakan arsitektur Service Mesh (Istio, Linkerd) dengan mTLS ketat dan otorisasi *SPIFFE/SPIRE* antar-layanan mikro untuk memastikan isolasi jaringan internal.
3. **CI/CD Shift-Left Security Pipeline:**
   * Terapkan ambang batas kegagalan (*Quality Gates*): Pipeline build wajib digagalkan (*exit code 1*) apabila ditemukan kerentanan dengan tingkat keparahan *High* atau *Critical* pada fase scan SCA/SAST.

---

## 16. Hands-on Lab Step-by-Step

### Skenario Lab
Mendiagnosis kerentanan Mass Assignment pada endpoint pendaftaran pengguna dan mengotomatiskan inspeksi SAST menggunakan Semgrep.

#### Langkah 1: Eksplorasi Kode Rentan
Simpan kode berikut sebagai `server.js`:

```javascript
const express = require('express');
const app = express();
app.use(express.json());

let usersDb = [];

// Endpoint Rentan Mass Assignment
app.post('/api/users', (req, res) => {
  // ANTI-PATTERN: Mengambil seluruh payload req.body tanpa filtrasi properti
  const userData = req.body;
  
  // Set default role jika tidak terdefinisi (bisa ditimpa oleh payload jahat)
  if (!userData.role) {
    userData.role = 'standard_user';
  }

  userData.id = usersDb.length + 1;
  usersDb.push(userData);

  return res.status(201).json({ status: 'success', user: userData });
});

app.listen(3000, () => console.log('Lab running on port 3000'));
```

#### Langkah 2: Simulasi Eksploitasi
Jalankan server dan kirimkan permintaan via `curl`:

```bash
# Inisialisasi dependensi
npm install express

# Jalankan server
node server.js &

# Kirim payload manipulasi role secara langsung
curl -s -X POST http://localhost:3000/api/users \
  -H "Content-Type: application/json" \
  -d '{"username": "attacker", "email": "att@corp.local", "role": "superadmin"}' | jq
```

*Output yang diobservasi:*
```json
{
  "status": "success",
  "user": {
    "username": "attacker",
    "email": "att@corp.local",
    "role": "superadmin",
    "id": 1
  }
}
```
*Analisis:* Penyerang berhasil mengeskalasi hak akses menjadi `superadmin` karena backend mengikat seluruh objek masukan tanpa validasi.

#### Langkah 3: Remediasi Kode Menggunakan Data Transfer Object (DTO)
Modifikasi implementasi pada `server.js`:

```javascript
// SECURE PATTERN: Strict Property Whitelisting
app.post('/api/users', (req, res) => {
  const { username, email } = req.body;

  if (!username || !email) {
    return res.status(400).json({ error: 'Username dan email wajib diisi' });
  }

  const sanitizedUser = {
    id: usersDb.length + 1,
    username: String(username),
    email: String(email),
    role: 'standard_user' // Nilai statis dari sistem, tidak bisa dimanipulasi dari luar
  };

  usersDb.push(sanitizedUser);
  return res.status(201).json({ status: 'success', user: sanitizedUser });
});
```

#### Langkah 4: Verifikasi Pipeline DevSecOps dengan Semgrep
Jalankan scanning SAST lokal menggunakan aturan Semgrep custom untuk mendeteksi penugasan langsung `req.body`:

```bash
# Jalankan Semgrep CLI secara transparan di direktori kerja
docker run --rm -v "${PWD}:/src" returntocorp/semgrep semgrep \
  --config=p/javascript \
  --error
```

---

## 17. Real-world Case Study & Incident Analysis Enterprise

### Insiden: Pelanggaran Data Melalui Broken Object Level Authorization (BOLA) pada Platform Layanan Finansial
* **Latar Belakang:** Sebuah institusi perbankan digital meluncurkan API antarmuka mobile baru untuk mengunduh laporan mutasi rekening format PDF.
* **Vektor Serangan:** 
  Endpoint yang dihubungi oleh aplikasi: `GET /api/v2/statements?account_number=ACC-99281`. Penyerang menyadari bahwa meskipun token otentikasi JWT valid diwajibkan pada header `Authorization`, sistem gateway hanya memverifikasi *apakah token valid*, tetapi mikroservis rekening gagal memverifikasi *apakah pemegang token adalah pemilik sah dari `account_number` tersebut*.
* **Eksfiltrasi Data:**
  Penyerang menulis skrip otomatisasi untuk melakukan enumerasi seluruh blok nomor akun dari rentang `ACC-00001` hingga `ACC-99999`, mengekstraksi ratusan ribu berkas laporan transaksi finansial sensitif.
* **Akar Masalah (Root Cause):**
  Pemisahan logika autentikasi (dikelola oleh centralized API Gateway) dan otorisasi objek (diasumsikan sudah ditangani oleh database layer tanpa implementasi tenancy isolation).
* **Solusi Arsitektural Permanen:**
  1. Penghapusan identifier akun mentah pada parameter query; beralih menggunakan subjek token terenkripsi (`/api/v2/statements/me`).
  2. Implementasi middleware *Policy Decision Point* (PDP) menggunakan Open Policy Agent (OPA) yang mengonfirmasi relasi kepemilikan objek pada level data-access sebelum query dieksekusi.

---

## 18. Quiz Pemahaman & Challenge

### Pertanyaan Konseptual

1. Mengapa penggunaan antarmuka WAF (Web Application Firewall) berbasis signature tidak cukup untuk memitigasi kerentanan Broken Object Level Authorization (BOLA)?
2. Dalam implementasi OAuth 2.0 Authorization Code Grant, apa fungsi kriptografis dari parameter `code_challenge` dan `code_verifier` (PKCE - RFC 7636), dan serangan apa yang secara spesifik dinetralkan oleh mekanisme ini?
3. Sebutkan perbedaan mendasar antara mekanisme SSRF Berbasis Respons (*In-band/Direct SSRF*) dan Blind SSRF (*Out-of-band SSRF*), serta jelaskan metode verifikasi untuk mendeteksi Blind SSRF!

### Diagnostic Challenge
Diberikan cuplikan kebijakan Content Security Policy (CSP) berikut:
```http
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com 'unsafe-eval'; object-src 'none';
```
*Tugas:* Identifikasi potensi vektor bypass eksekusi XSS yang masih terbuka pada konfigurasi di atas jika aplikasi mengizinkan penyerang mengunggah berkas teks atau memanggil pustaka rentan dari CDN yang diizinkan!

---

## 19. Summary & Key Takeaways

* **Pertahanan Lapik (Defense-in-Depth):** Tidak ada satu lapisan tunggal (WAF, Gateway, atau Framework) yang mampu menyelesaikan masalah keamanan secara terisolasi. Otorisasi harus ditegakkan pada lapisan aplikasi paling bawah sedekat mungkin dengan sumber data.
* **Integritas Kontekstual API:** BOLA dan Mass Assignment bukan merupakan cacat sintaksis melainkan cacat semantik dan logika bisnis. Scanning statis tradisional sering melewatkan masalah ini, sehingga pemodelan ancaman (*threat modeling*) pada fase desain skema data mutlak diperlukan.
* **Zero Trust In Egress:** Penanganan SSRF tidak cukup dengan membuat *denylist* domain, melainkan membutuhkan restriksi tingkat jaringan sistemik (segmentasi VPC, pemblokiran rute link-local metadata, penegakan IMDSv2, serta isolasi transport HTTP).
* **Otomasi Keamanan Deterministik:** DevSecOps yang efektif bergantung pada *automated feedback loop* cepat di CI/CD pipeline melalui konvergensi SAST, SCA, dan penegakan policy-as-code untuk mencegah regresi keamanan di lingkungan produksi.

---

## 20. Referensi Resmi & Standar Keamanan

* **OWASP Foundation:** 
  * *OWASP Top 10: 2021* (A01: Broken Access Control, A03: Injection, A10: SSRF).
  * *OWASP API Security Top 10: 2023* (API1: BOLA, API2: Broken Authentication, API3: BOPLA).
  * *OWASP Application Security Verification Standard (ASVS) v4.0.3.*
* **NIST (National Institute of Standards and Technology):**
  * *NIST Special Publication 800-53, Revision 5:* Security and Privacy Controls for Information Systems and Organizations (Control Families: AC - Access Control, SI - System and Information Integrity).
  * *NIST SP 800-95:* Guide to Secure Web Services.
* **IETF RFC Standards:**
  * *RFC 6749:* The OAuth 2.0 Authorization Framework.
  * *RFC 7519:* JSON Web Token (JWT).
  * *RFC 7636:* Proof Key for Code Exchange by OAuth Public Clients (PKCE).
* **MITRE ATT&CK Enterprise Framework:**
  * *T1190:* Exploit Public-Facing Application.
  * *T1059:* Command and Scripting Interpreter.
  * *T1552:* Unsecured Credentials.