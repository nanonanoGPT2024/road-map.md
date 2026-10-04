# BAB 09: Quiz, Challenge, & Knowledge Check
**Keamanan HTML: Sanitasi DOM, CSP, dan Isolasi Sandbox**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **DOM-based XSS vs. Stored/Reflected XSS:**
   Jelaskan perbedaan fundamental siklus hidup eksekusi payload antara DOM-based XSS dengan Reflected/Stored XSS dari perspektif pemrosesan parser browser dan server. Mengapa manipulasi *execution sink* seperti `element.innerHTML` atau `document.write()` sepenuhnya dapat mengeksekusi script jahat tanpa payload tersebut pernah menyentuh HTTP response server?

2. **Dilema Keamanan Atribut `sandbox` pada `<iframe>`:**
   Atribut `sandbox` pada elemen `<iframe>` secara default menerapkan isolasi ketat (*least privilege*). Mengapa kombinasi token `allow-scripts` dan `allow-same-origin` secara bersamaan dianggap sebagai *critical security misconfiguration* fatal jika frame tersebut menyajikan konten yang berasal dari origin yang sama dengan aplikasi induk?

3. **Mekanisme Kerja Content Security Policy (CSP):**
   Bagaimana browser mengevaluasi direktif CSP saat melakukan *resource fetching* dan eksekusi kode? Jelaskan perbedaan operasional mendasar antara pendekatan *allowlisting domain* (contoh: `script-src https://cdn.example.com`) versus *cryptographic nonce-based strict CSP* (contoh: `script-src 'nonce-r@nd0m' 'strict-dynamic'`), serta mengapa pendekatan allowlisting kini dianggap usang (*deprecated approach*) dalam pertahanan web modern.

4. **Kelemahan Sanitasi Berbasis Regular Expression (Regex):**
   Secara arsitektural, mengapa regular expression tidak dapat diandalkan untuk melakukan sanitasi atau *parsing* HTML (misalnya stripping tag `<script>` atau atribut `onload`)? Hubungkan penjelasan Anda dengan spesifikasi *HTML5 tokenization*, *tree construction state machine*, dan konsep *nested parsing contexts*.

5. **Prinsip Dasar Trusted Types API:**
   Bagaimana Trusted Types API memblokir kerentanan DOM XSS secara default di level runtime browser? Jelaskan peran *Type Enforcement* terhadap DOM sinks (seperti assignment ke `innerHTML`) dan bagaimana arsitektur ini memindahkan beban audit keamanan dari ribuan baris kode aplikasi ke satu titik pembuatan *policy*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anatomi Mutation XSS (mXSS):**
   Jelaskan secara mendalam siklus *deserialization-mutation-reserialization* yang memicu Mutation XSS (mXSS). Bagaimana sebuah markup HTML yang lolos dari engine sanitasi (karena dianggap aman dan tidak memiliki executable script) dapat bermutasi menjadi vektor serangan aktif saat di-parse ulang dan direkonstruksi ke dalam live DOM tree oleh browser?

2. **CSP Bypass via Gadget & Framework Interaction:**
   Sebuah aplikasi menerapkan CSP berikut:
   ```http
   Content-Security-Policy: default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com;
   ```
   Aplikasi tidak menggunakan inline script. Jelaskan bagaimana penyerang dapat mengeksploitasi direktif ini menggunakan *client-side template injection* (CSTI) atau teknik *AngularJS/UI gadget bypass* via library lawas yang di-host di CDN publik tersebut tanpa melanggar kebijakan CSP yang dideklarasikan.

3. **Isolasi Proses dan Spectre Mitigation via COOP/COEP:**
   Jelaskan hubungan teknis antara isolasi browsing context (HTML rendering context) dengan *cross-origin isolation*. Mengapa penggunaan API beresolusi tinggi seperti `SharedArrayBuffer` dan `performance.now()` presisi mikrodetik mewajibkan implementasi header `Cross-Origin-Opener-Policy: same-origin` (COOP) dan `Cross-Origin-Embedder-Policy: require-corp` (COEP)?

4. **Debugging dan Strategi Migrasi via CSP-Report-Only:**
   Anda bertugas mengimplementasikan strict CSP pada sistem monolithic enterprise berusia 10 tahun yang memiliki ribuan baris inline script warisan. Jelaskan arsitektur pipeline implementasi tanpa risiko downtime menggunakan header `Content-Security-Policy-Report-Only`, `report-to`/`Reporting-Endpoints`, teknik ekstraksi *hash-based allowlisting* (`sha256-...`), dan cara menangani noise violation reports yang dihasilkan oleh browser extensions pihak klien.

5. **Intersepsi DOMPurify Hooks pada Kasus Edge-case Foreign Object:**
   Saat melakukan sanitasi dokumen SVG dan MathML yang disematkan dalam HTML5, vector injection sering kali lolos melalui *namespace confusion* (misalnya eksploitasi elemen `<style>` di dalam `<svg>` atau integrasi tag `<annotation-xml>`). Bagaimana mekanisme hook DOMPurify (seperti `uponSanitizeElement` dan `afterSanitizeAttributes`) beroperasi pada level Abstract Syntax Tree (AST)/DOM Nodes untuk menetralkan *foreign object context switching* ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Telemetry Denial-of-Service & Lockout pada Migrasi CSP Enterprise
Sebuah platform e-commerce dengan trafik 15.000 request per detik mengaktifkan *Strict Nonce-based CSP* secara langsung di production environment via reverse proxy/edge gateway:
```http
Content-Security-Policy: default-src 'self'; script-src 'nonce-XYZ' 'strict-dynamic'; report-uri /api/csp-report;
```
Dalam waktu 3 menit:
1. Layanan backend reporting `/api/csp-report` mengalami crash akibat CPU starvation dan disk I/O saturation (terima 40.000 HTTP POST/detik).
2. Sebagian besar pengguna di wilayah tertentu melaporkan antarmuka web rusak total (*unusable UI*), tombol *checkout* macet, dan keranjang belanja kosong.
3. Tim QA menemukan bahwa nonce `'XYZ'` di-cache oleh intermediate CDN edge node untuk seluruh pengguna selama TTL 300 detik.

* **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat 3 kegagalan arsitektur dalam pipeline deployment CSP di atas.
  2. Mengapa *caching* nonce oleh CDN menyebabkan browser memblokir seluruh inline script aplikasi, dan bagaimana desain arsitektur yang benar untuk injeksi cryptographic nonce dalam lingkungan microservices berbasis CDN?
  3. Rancang strategi mitigasi pelaporan telemetry (*reporting flood*) agar endpoint analytics terlindungi dari DoS tanpa kehilangan visibilitas insiden keamanan riil.

---

### Skenario B: Mutation XSS (mXSS) pada Collaborative Rich-Text Document
Platform kolaborasi dokumen online mengizinkan pengguna memformat teks menggunakan HTML WYSIWYG editor. Alur penyimpanan dan rendering dokumen adalah sebagai berikut:
1. Klien mengirim konten HTML editor ke server melalui WebSocket.
2. Server menjalankan sanitasi menggunakan library sanitizer berbasis engine Node.js (*jsdom*).
3. Server mendistribusikan HTML bersih ke klien lain.
4. Klien penerima langsung mengeksekusi: `editorContainer.innerHTML = sanitizedPayload;`.

Seorang penyerang berhasil mengeksekusi arbitrary JavaScript di browser pengguna lain dengan payload manipulasi namespace MathML/SVG:
```html
<math><mtext><table><mglyph><style><!--</style><img src="x" onerror="stealSessionCookie()">
```

* **Pertanyaan Diagnostik:**
  1. Mengapa library sanitizer server-side berbasis *virtual DOM engine* (seperti jsdom) gagal mendeteksi ancaman ini sementara engine parser HTML5 browser (seperti Blink/Gecko) mengeksekusinya sebagai kode aktif?
  2. Analisis bagaimana parsing flag berubah saat browser berpindah dari *Foreign Content Parsing Mode* (MathML/SVG) ke *HTML Parsing Mode* pada konstruksi elemen di atas, sehingga tag `<img>` yang semula berada di dalam comment block `<style>` diekstraksi ke live DOM.
  3. Rekonstruksi arsitektur pipeline sanitasi dan rendering HTML dokumen tersebut dari hulu ke hilir untuk memitigasi mXSS secara deterministik (rekomendasikan API modern, lokasi sanitasi yang tepat, dan konfigurasi sanitizernya).

---

### Skenario C: Isolasi Arsitektur Third-Party Financial Widget
Sebuah institusi perbankan mengintegrasikan widget analisis pasar dari vendor pihak ketiga ke dalam dashboard internet banking nasabah. 
* Persyaratan Fungsional: Widget membutuhkan akses network mandiri untuk mengambil feed data real-time via WebSocket/Fetch, memerlukan rendering grafik interaktif, dan harus menerima payload identitas token transaksi dari aplikasi perbankan (host frame).
* Batasan Keamanan Kritis: Widget **tidak boleh** memiliki akses ke DOM aplikasi perbankan, **tidak boleh** mengakses cookie sesi nasabah (`document.cookie`), **tidak boleh** mengeksekusi navigasi top-level (`window.top.location`), dan **tidak boleh** menyematkan iframe aplikasi bank ke domain luar (mencegah Clickjacking).

* **Pertanyaan Diagnostik:**
  1. Konfigurasikan atribut elemen `<iframe>` (secara detail dengan atribut `sandbox`, `allow`, dan security properties lainnya) yang memenuhi batasan di atas tanpa melumpuhkan fungsionalitas widget vendor.
  2. Tuliskan implementasi arsitektur komunikasi bidirectional berbasis `window.postMessage` yang aman antara host window dan widget iframe, mencakup: verifikasi origin, pencegahan kebocoran transfer payload, dan mitigasi event listener pollution.
  3. Header HTTP Keamanan (CSP, Frame-Options, Framing Protections) apa yang wajib dipasang pada sisi aplikasi perbankan (host) dan pada sisi server widget (embedee) untuk menjamin isolasi total?

---

## 4. Chapter Challenge

### Tantangan Praktis: Hardened Sandboxed Micro-Frontend & Strict Sanitization Pipeline

#### Problem Statement
Anda ditugaskan merancang modul perender konten dinamis (*Safe Content Display Module*) untuk enterprise dashboard. Modul ini menerima input HTML tidak tepercaya dari user-generated content (berisi format teks, tabel, gambar eksternal) dan merender plugin/widget kustom pihak ketiga via HTML iframe. Sistem Anda harus kebal terhadap DOM-based XSS, Mutation XSS (mXSS), CSS injection attacks, serta memutus akses frame ke parent context.

#### Requirements
1. **Trusted Types & DOMPurify Integration:**
   * Wajib mengaktifkan `Trusted Types` enforcement pada level document.
   * Buat kebijakan (*policy*) Trusted Types bernama `dom-hardener` yang memanfaatkan `DOMPurify`.
   * Aturan sanitasi: Izinkan tag `<b>`, `<i>`, `<p>`, `<table>`, `<tr>`, `<td>`, `<img>`, `<a>`. Drop seluruh atribut event handler (`on*`), larang skema pseudo-protokol (`javascript:`, `data:`, `vbscript:`), dan hapus elemen berbahaya (`<script>`, `<object>`, `<embed>`, `<style>`, `<form>`).
   * Terapkan konfigurasi mitigasi mXSS (`RETURN_DOM_FRAGMENT: false`, `FORCE_BODY: true`, penanganan namespace SVG/MathML dinonaktifkan).

2. **Hardened Sandboxed Frame Generator:**
   * Buat factory function JavaScript yang menghasilkan elemen `<iframe>` untuk memuat HTML string tidak tepercaya.
   * Atribut `sandbox` harus dikonfigurasi dengan prinsip hak akses terendah: izinkan rendering visual dan pemrosesan form terisolasi, tetapi larang eksekusi script dan akses parent session.
   * Gunakan atribut `srcdoc` untuk rendering, dikombinasikan dengan inline CSP yang didefinisikan via meta-tag di dalam dokumen `srcdoc`.

3. **Secure Handshake via PostMessage (Defense-in-Depth):**
   * Buat helper module untuk parent frame dan child iframe yang memfasilitasi pertukaran data secara aman:
     * Pengirim pesan wajib mendeklarasikan `targetOrigin` secara eksplisit (dilarang menggunakan wildcard `'*'`).
     * Penerima pesan wajib mengecek integritas `event.origin` sebelum memproses data.

#### Constraints
* Tidak boleh menggunakan library eksternal selain `DOMPurify` (diasumsikan sudah ter-load di namespace `window.DOMPurify`).
* Zero violation terhadap aturan: `no-eval`, no `unsafe-inline`, no `unsafe-hashes`.
* Skrip harus ditulis dalam standard JavaScript Modern (ES2022+), performan, serta menyertakan penanganan error secara eksplisit.

#### Expected Output
Sajikan solusi dalam blok kode terstruktur yang mencakup:
1. Deklarasi HTTP Response Header (CSP Policy string yang memuat enforcement Trusted Types).
2. Implementasi JavaScript:
   * Setup Trusted Types Policy.
   * Fungsi sanitasi dan injection ke live DOM.
   * Generator secure sandboxed `iframe`.
   * Secure `postMessage` protocol implementation.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal parsing browser: perbedaan antara context HTML, Foreign Content (SVG/MathML), dan bagaimana browser parser state machine bertransisi saat membaca token.
- [ ] Mengapa *execution sinks* (`innerHTML`, `outerHTML`, `document.write`, `insertAdjacentHTML`) rentan terhadap DOM XSS dan bagaimana mekanisme kerjanya.
- [ ] Perbedaan fungsionalitas seluruh token direktif pada atribut `sandbox` `<iframe>` (`allow-scripts`, `allow-same-origin`, `allow-top-navigation`, `allow-popups`, dll).
- [ ] Anatomi header Content Security Policy (CSP): direktif fetch (`default-src`, `script-src`, `style-src`, `connect-src`), direktif framing (`frame-ancestors`, `child-src`), dan direktif enforcement (`require-trusted-types-for`, `trusted-types`).
- [ ] Konsep kriptografis CSP Nonce: persyaratan entropy, siklus hidup per-request HTTP, dan interaksinya dengan caching server/CDN.
- [ ] Mekanisme kerja Mutation XSS (mXSS) dan alasan fundamental mengapa parser server-side sering kali menghasilkan DOM AST yang berbeda dengan parser browser.
- [ ] Isolasi browsing context tingkat proses sistem operasi menggunakan header COOP, COEP, dan CORP.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar tag HTML atau atribut SVG yang valid menurut spesifikasi W3C/WHATWG.
- [ ] String hash SHA-256 spesifik dari inline script tertentu.
- [ ] Semua konfigurasi internal regex atau array tag whitelist di dalam source code mentah DOMPurify.
- [ ] Seluruh vendor-specific prefix pada implementasi legacy CSP lama (misal: `-webkit-csp`, `X-Content-Security-Policy`).

### Saya harus bisa melakukan:
- [ ] Merancang dan mengonfigurasi header CSP Level 3 berbasis Nonce yang ketat tanpa bergantung pada teknik allowlisting domain yang rentan bypass.
- [ ] Mengonfigurasi dan mengaktifkan **Trusted Types API** di aplikasi web modern untuk mengunci DOM injection sinks.
- [ ] Melakukan sanitasi input HTML kaya (*rich HTML*) secara deterministik menggunakan `DOMPurify` dengan konfigurasi hardening anti-mXSS.
- [ ] Mengisolasi komponen pihak ketiga yang tidak tepercaya (*untrusted 3rd-party widget*) menggunakan kombinasi tag `<iframe>`, restricted `sandbox`, dan secure `postMessage` bus.
- [ ] Menganalisis dan mendebug CSP Violation Reports untuk mendeteksi serangan nyata versus kesalahan penulisan kode (*false positive*).
- [ ] Melakukan refactoring kode legacy yang menggunakan unsafe DOM manipulation (`element.innerHTML = data`) menjadi safe alternatives (`element.textContent`, `element.append`, atau sanitized Trusted Type assignments).