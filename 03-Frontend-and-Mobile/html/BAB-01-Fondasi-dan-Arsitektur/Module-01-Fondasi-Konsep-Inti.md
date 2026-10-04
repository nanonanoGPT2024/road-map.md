# Bab 01: Fondasi HTML & Dokumen Web Modern
## Module 01: Arsitektur Dokumen HTML, Parsing Engine, dan DOM Tree Construction

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengartikulasikan siklus hidup parsing HTML dari *byte stream*, decoding karakter, tokenisasi, hingga konstruksi *Document Object Model* (DOM) berdasarkan spesifikasi WHATWG HTML.
- Menganalisis dan mengeliminasi degradasi performa akibat *parser-blocking resource* serta *speculative parsing failure*.
- Mengonfigurasi struktur fondasi dokumen HTML5 produksi yang deterministik, kebal terhadap *quirks mode*, dan patuh pada standar keamanan modern.
- Mendiagnosis serta merekonstruksi kerusakan parsing tree yang disebabkan oleh *malformed markup* menggunakan pemahaman mendalam tentang *error-tolerant parsing algorithm*.

---

### 2. Conceptual Foundation (Fondasi Konseptual)
HTML (*HyperText Markup Language*) bukan sekadar format deklarasi tata letak teks, melainkan antarmuka serialisasi untuk pohon komputasi runtime yang disebut DOM. Mesin peramban modern (seperti Blink pada Chromium, WebKit pada Safari, dan Gecko pada Firefox) tidak memproses HTML secara paralel seperti parser compiler tradisional (misalnya parser C++ atau Rust yang berbasis LLVM), melainkan menggunakan *state machine parser* deterministik dua fase yang toleran terhadap kegagalan (*error-tolerant*).

Pondasi utama HTML bertumpu pada hukum kontinuitas parsing: dokumen tidak harus selesai diunduh secara penuh untuk mulai diproses. Parser browser membaca data dalam bentuk bongkahan (*chunks*) jaringan melalui *stream* I/O tak-sinkron (*asynchronous byte streams*). Setiap *chunk* melewati tahap:
1. **Network Byte Stream**: Paket data TCP mentah diterima oleh browser engine.
2. **Character Encoding Sniffing & Decoding**: Konversi deretan byte menjadi deretan karakter Unicode (UTF-8).
3. **Tokenization (Lexical Analysis)**: Karakter dikonversi menjadi unit token seperti `StartTag`, `EndTag`, `Character`, `Comment`, atau `DOCTYPE`.
4. **Tree Construction (Syntactic Analysis)**: Token memicu manipulasi *in-memory* langsung pada objek hierarki `Document` dan `Node` melalui tumpukan elemen terbuka (*stack of open elements*).

---

### 3. The "Why" (Mengapa Hal Ini Penting)
Banyak insinyur perangkat lunak menganggap HTML adalah sintaksis sepele yang hanya membutuhkan tag pembuka dan penutup. Anggapan ini keliru di level arsitektur produksi:
- **Biaya Parser-Blocking**: Memahami bagaimana parser berinteraksi dengan skrip eksternal dan lembar gaya (*stylesheets*) adalah batas pembeda antara situs dengan *First Contentful Paint* (FCP) 800ms dan situs dengan FCP 4.5 detik.
- **Konsistensi Lintas Lingkungan**: Ketidakhadiran deklarasi `<!DOCTYPE html>` memaksa mesin browser mengeksekusi *Quirks Mode*, menghidupkan kembali bug layout Netscape Navigator 4 dan Internet Explorer 5 yang merusak box-model CSS modern.
- **Integritas Parsing**: Kesalahan penempatan tag (misalnya meletakkan `<div>` di dalam `<p>`) secara otomatis memicu algoritma koreksi otomatis (*adoption agency algorithm*), yang mengalokasikan memori ekstra secara tersembunyi dan memecah struktur DOM secara tak terduga.

---

### 4. The "What" (Spesifikasi Teknis & Terminologi)
Berdasarkan spesifikasi resmi WHATWG HTML Living Standard:
- **`DOCTYPE`**: Direktif penanda standar dokumen. Sintaks `<!DOCTYPE html>` adalah representasi string minimal yang secara eksplisit menginstruksikan browser untuk beroperasi dalam *Full Standards Mode*.
- **Token**: Unit leksikal independen yang dihasilkan oleh tokenizer state machine. Terdiri dari 6 kelas token: `DOCTYPE`, `StartTag`, `EndTag`, `Comment`, `Character`, dan `EndOfFile`.
- **Stack of Open Elements**: Struktur data *last-in-first-out* (LIFO) konseptual yang digunakan oleh fase *Tree Construction* untuk melacak node mana yang saat ini sedang aktif menerima anak (*child nodes*).
- **Foster Parenting**: Mekanisme khusus dalam spesifikasi tree construction di mana konten tabel yang ditempatkan secara tidak sah (di luar `<td>` atau `<th>`) dipaksa keluar dari tabel dan dimasukkan tepat sebelum elemen `<table>` di dalam DOM tree.
- **Speculative / Preload Scanner**: Parser sekunder ringan berkecepatan tinggi yang memindai byte stream secara paralel sebelum DOM tree utama dibangun untuk menemukan resource eksternal (`<link>`, `<script>`, `<img>`) guna langsung mengantrekan permintaan jaringan.

---

### 5. The "How" (Mekanisme Operasional/Workflow)
Alur operasional dari URL Fetch hingga DOM Ready:

```
[Raw TCP Packets] 
       │
       ▼
1. Byte Stream Decoder ───► Deteksi BOM / Header Content-Type / Meta Charset
       │
       ▼ (Unicode Characters)
2. Tokenizer (State Machine)
       │ ◄─── Feedback Loop (Parser Control via <script> execution)
       ▼ (Tokens: StartTag, Character, EndTag, etc.)
3. Tree Construction
       │
       ├──► Stack of Open Elements (Menentukan relasi Parent-Child)
       ├──► Foster Parenting (Jika mendeteksi malformed table data)
       └──► Adoption Agency Algorithm (Koreksi format nesting ilegal)
       │
       ▼
[DOM Tree Instantiated in Memory]
```

Tahap koreksi token terjadi saat parser menemukan tag penutup yang tidak cocok dengan puncak stack:
1. Parser mengecek apakah tag penutup ada di dalam *scope* saat ini.
2. Jika ada, parser memunculkan (*pop*) elemen dari *stack of open elements* sampai elemen yang cocok ditemukan, secara otomatis menutup elemen-elemen yang tertinggal.
3. Node yang dihasilkan langsung didaftarkan ke representasi C++ objek browser (misalnya `HTMLDivElement` pada Blink/V8).

---

### 6. System Architecture Diagram (Diagram ASCII)

Berikut adalah interaksi antara Main Parser, Speculative Scanner, dan JavaScript Engine saat parsing dokumen HTML:

```
+-------------------------------------------------------------------------------+
|                             BROWSER MAIN PROCESS                              |
+-------------------------------------------------------------------------------+
                                      │ Network Bytes
                                      ▼
+-------------------------------------------------------------------------------+
|                               RENDERER PROCESS                                |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   |                        HTML PRELOAD SCANNER                           |   |
|   |   (Non-blocking token scanning: Menemukan src/href untuk fetch awal)  |   |
|   +-----------------------------------------------------------------------+   |
|                                     │                                         |
|                                     │ Fetch requests                          |
|                                     ▼                                         |
|   +-----------------------------------------------------------------------+   |
|   |                           NETWORK STACK                               |   |
|   +-----------------------------------------------------------------------+   |
|                                     ▲                                         |
|                                     │ Chunks data                             |
|                                     ▼                                         |
|   +-----------------------------------------------------------------------+   |
|   |                         MAIN PARSER PIPELINE                          |   |
|   |                                                                       |   |
|   |   +------------------+    Tokens     +----------------------------+   |   |
|   |   |  HTML Tokenizer  | ------------> |     Tree Construction      |   |   |
|   |   +------------------+               +----------------------------+   |   |
|   |            ▲                                       │                  |   |
|   |            │ (Resume/Re-enter)                     │ Mutates          |   |
|   |            │                                       ▼                  |   |
|   |   +------------------+               +----------------------------+   |   |
|   |   | JavaScript Engine| <-----------> |    DOM Tree (In-Memory)    |   |   |
|   |   |  (V8/SpiderM.)   |  Script Block |                            |   |   |
|   |   +------------------+               +----------------------------+   |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
```

---

### 7. Primitive/Simple Code Example (Implementasi Minimal)

Dokumen HTML5 struktural valid minimal absolut menurut spesifikasi WHATWG:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Sistem Minimal</title>
</head>
<body>
  <h1>Status Sistem</h1>
  <p>Sistem operasional.</p>
</body>
</html>
```

*Catatan Teknis:* Meskipun tag `<html>`, `<head>`, dan `<body>` secara teknis bersifat opsional dalam spesifikasi parsing (parser akan otomatis menginferensinya jika hilang), penghilangan eksplisit tag-tag tersebut merupakan anti-pola pada level rekayasa perangkat lunak karena membingungkan parser spec dan linting tool.

---

### 8. Production/Practical Code Example (Implementasi Produksi)

Berikut adalah skeleton arsitektur dokumen HTML5 enterprise-grade yang siap diproduksi:

```html
<!DOCTYPE html>
<html lang="id" dir="ltr">
<head>
  <!-- 1. Enkoding Karakter: Wajib berada di 1024 byte pertama -->
  <meta charset="UTF-8">

  <!-- 2. Responsive Viewport Meta: Wajib untuk mobile layout rendering -->
  <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">

  <!-- 3. Engine & Platform Directives -->
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="format-detection" content="telephone=no">

  <title>Dashboard Analitik Performa | Enterprise Engine</title>

  <!-- 4. Security Policy: Mencegah XSS dan injeksi resource tak berizin -->
  <meta http-equiv="Content-Security-Policy" 
        content="default-src 'self'; script-src 'self' https://cdn.enterprise.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; base-uri 'self'; form-action 'self';">

  <!-- 5. Optimasi Resource Hints: Preconnect dan DNS-Prefetch ke CDN kritis -->
  <link rel="preconnect" href="https://cdn.enterprise.com" crossorigin>
  <link rel="dns-prefetch" href="https://cdn.enterprise.com">

  <!-- 6. Critical CSS di-injeksi inline untuk mengeliminasi render-blocking RTT -->
  <style>
    :root { --font-fallback: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font-fallback); background-color: #0f172a; color: #f8fafc; min-height: 100vh; }
    .layout-boundary { display: grid; grid-template-rows: auto 1fr auto; min-height: 100vh; }
    .hidden-accessible { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0; }
  </style>

  <!-- 7. Asynchronous Stylesheet Loading (Non-critical CSS) -->
  <link rel="preload" href="/assets/css/main.chunk.css" as="style" onload="this.onload=null;this.rel='stylesheet'">
  <noscript><link rel="stylesheet" href="/assets/css/main.chunk.css"></noscript>

  <!-- 8. Non-blocking Deferred Scripts -->
  <script src="/assets/js/runtime.bundle.js" defer></script>
  <script src="/assets/js/analytics.bundle.js" async></script>
</head>
<body>
  <!-- Aksesibilitas: Skip Link untuk keyboard navigation -->
  <a href="#main-content" class="hidden-accessible focus:not-sr-only">Langsung ke Konten Utama</a>

  <div class="layout-boundary">
    <header role="banner">
      <nav aria-label="Navigasi Utama">
        <span>Enterprise System</span>
      </nav>
    </header>

    <main id="main-content" role="main">
      <h1>Metrik Agregasi Server</h1>
      <section aria-labelledby="status-header">
        <h2 id="status-header">Node Aktif</h2>
        <p>Kluster beroperasi dalam toleransi normal.</p>
      </section>
    </main>

    <footer role="contentinfo">
      <p>&copy; 2026 Enterprise Core Architecture. Hak cipta dilindungi undang-undang.</p>
    </footer>
  </div>
</body>
</html>
```

---

### 9. Step-by-Step Code Walkthrough (Analisis Kode Baris demi Baris)

- `<!DOCTYPE html>`: Menginstruksikan layout engine peramban untuk beralih ke *No-Quirks Mode* (juga dikenal sebagai *Full Standards Mode*). Tanpa deklarasi ini, peramban mengeksekusi *Quirks Mode*, mengubah perhitungan dimensi elemen CSS (misalnya properti `width` dan `height` akan mencakup `padding` dan `border` secara cacat).
- `<html lang="id" dir="ltr">`: Menentukan lokalisasi bahasa dokumen untuk mesin penerjemah, text-to-speech engine, serta *Screen Reader* (A11y). Atribut `dir="ltr"` secara eksplisit menetapkan orientasi penulisan dari kiri ke kanan.
- `<meta charset="UTF-8">`: Menginstruksikan parser untuk mendekode stream byte menggunakan UTF-8. **Wajib ditempatkan sedini mungkin** (maksimal dalam batas 1024 byte awal file). Jika diletakkan terlalu jauh di bawah, parser mungkin mulai mendekode menggunakan fallback encoding (misalnya ISO-8859-1), lalu menemukan tag ini dan terpaksa membuang seluruh token yang telah dibuat untuk memulai parsing ulang dari byte 0 (*encoding restart*).
- `<meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">`: Menghilangkan delay 300ms tap pada layar sentuh dan memaksa viewport rendering logical matches dengan resolusi fisik device, bukan rendering virtual desktop 980px.
- `<meta http-equiv="Content-Security-Policy" ...>`: Lapisan pertahanan pertama arsitektur terhadap serangan *Cross-Site Scripting* (XSS) dan *Data Exfiltration*. Ini memberi tahu parser untuk langsung menolak skrip yang diinjeksikan secara tidak sah via basis domain non-whitelisted.
- `<link rel="preconnect" ...>`: Menginstruksikan layer network browser untuk melakukan *DNS Lookup*, *TCP Handshake*, dan negosiasi *TLS termination* ke server target bahkan sebelum parser meminta berkas CSS/JS dari host tersebut.
- `<script ... defer>`: Menjadwalkan pengunduhan skrip secara paralel terhadap parsing HTML tanpa memblokir pembuatan DOM. Skrip dieksekusi secara berurutan sesuai posisinya di HTML tepat setelah tokenisasi HTML selesai, sebelum event `DOMContentLoaded`.

---

### 10. Edge Cases, Gotchas, and Pitfalls (Kasus Ekstrem & Jebakan Teknis)

#### Kasus A: Script Tag Parsing Hijacking
Jika Anda menyuntikkan data JSON mentah ke dalam tag `<script>`, string yang mengandung `</script>` akan langsung mematikan block script secara paksa karena tokenizer HTML bekerja dengan kecocokan string karakter mentah sederhana (*rawtext state termination*), bukan evaluasi sintaksis JS:

```html
<!-- JEBAKAN: Eksekusi JS akan rusak, sisa data terekspos sebagai teks HTML mentah -->
<script>
  const payload = { "comment": "</script><script>alert('pwned')</script>" };
</script>

<!-- SOLUSI BENAR: Serialisasi string dengan escape Unicode slash -->
<script>
  const payload = { "comment": "<\/script><script>alert('pwned')<\/script>" };
</script>
```

#### Kasus B: Adoption Agency Algorithm Abuse
Penyusunan nesting tag format inline yang saling tumpang tindih secara tidak teratur:

```html
<!-- KODE CACAT -->
<p>Dokumen <b>Format <i>Tumpang Tindih</p> Selesai</i></b>
```

Parser HTML5 tidak akan melempar *parse error exception*. Sebaliknya, ia mengeksekusi algoritma *Adoption Agency* yang sangat mahal. Parser akan mengkloning node `<b>` dan `<i>` secara internal untuk membungkus sisa teks, menghasilkan DOM Tree berikut:

```
p
 ├── #text: Dokumen 
 └── b
      ├── #text: Format 
      └── i
           └── #text: Tumpang Tindih
#text:  Selesai
```
Hasil: Node terpecah, ukuran tree bertambah, dan performa query selektor melambat.

---

### 11. Performance Implications (Dampak Performa & Alokasi Resource)

1. **Parser Blocking Behavior**: Tag `<script src="...">` standar (tanpa `async` atau `defer`) memblokir thread rendering utama. Alurnya:
   - Parser berhenti.
   - Network thread mengambil file JavaScript.
   - V8 Engine mengompilasi dan mengeksekusi file tersebut.
   - Parser HTML baru melanjutkan parsing sisa dokumen.
   Hal ini berpotensi membekukan konstruksi DOM selama ratusan milidetik.
2. **Memory Footprint**: Setiap tag HTML memicu instansiasi objek antarmuka DOM (C++ wrapper). Dokumen HTML dengan kedalaman nesting > 32 level atau jumlah node total > 1400 node membebani heap memory mobile browser dan meningkatkan overhead garbage collection secara eksponensial saat pembaruan layout (reflow).
3. **Speculative Preload Failure**: Penggunaan CSS `@import` di dalam tag `<style>` memblokir speculative scanner karena peramban tidak dapat menemukan URL aset hingga CSS parser internal selesai memproses blok stylesheet tersebut. Hindari `@import` pada jalur render kritis.

---

### 12. Security Considerations (Aspek Keamanan)

1. **DOM Clobbering**: Penamaan atribut `id` atau `name` sembarangan pada elemen HTML dapat menimpa properti global pada objek `window` atau `document`.
   ```html
   <!-- JEBAKAN DOM CLOBBERING -->
   <form id="config" name="url">
     <input id="path" value="malicious.site">
   </form>
   <script>
     // window.config sekarang merujuk ke HTMLFormElement, bukan object JS!
     if (window.config) {
       // Penyerang dapat membajak eksekusi dependensi script berikut
       fetch(window.config.path.value);
     }
   </script>
   ```
2. **Reverse Tabnabbing**: Menggunakan atribut `target="_blank"` pada tautan anchor tanpa relasi pengaman memungkinkan halaman baru yang dibuka mengakses objek `window.opener` halaman asal:
   ```html
   <!-- VULNERABLE -->
   <a href="https://external-untrusted.com" target="_blank">Partner</a>

   <!-- SECURE (HTML5 modern mengimplikasikan noopener, tapi eksplisit lebih aman) -->
   <a href="https://external-untrusted.com" target="_blank" rel="noopener noreferrer">Partner</a>
   ```

---

### 13. Architectural Trade-offs (Analisis Kompromi Teknis)

| Pendekatan Arsitektur | Keuntungan | Kompromi / Kerugian |
| :--- | :--- | :--- |
| **Inlining Critical Resources** (Critical CSS & Base64 Assets di `<head>`) | Menghilangkan *Round-Trip Time* (RTT) jaringan; FCP hampir instan pada *cold load*. | Menghilangkan kemampuan caching browser terpisah antar dokumen; ukuran file HTML dasar membengkak secara drastis (*payload bloat*). |
| **Monolithic Single HTML Page** (SSR HTML Utuh) | Sangat ramah SEO; parser streaming dapat langsung menyajikan *Meaningful Content*. | Konsumsi data transfer tinggi untuk navigasi berulang; beban CPU server bertambah akibat proses rendering markup terus-menerus. |
| **Shell HTML Minimalis** (SPA Architecture: satu `<div id="root">`) | Beban rendering server sangat rendah; perpindahan halaman klien sangat responsif. | FCP dan LCP sangat terhambat; SEO rapuh; *Time to Interactive* (TTI) tertekan karena bergantung pada JS bundle besar sebelum ada markup yang dapat digambar. |

---

### 14. Anti-Patterns & Bad Practices (Anti-Pola yang Harus Dihindari)

```html
<!-- ANTI-POLA: Praktik Rendering Terburuk -->
<html>
<!-- Kesalahan 1: Doctype hilang -> Memicu QUIRKS MODE -->
<head>
  <!-- Kesalahan 2: Script eksternal synchronous ditaruh sebelum CSS -->
  <script src="heavy-analytics.js"></script>
  
  <!-- Kesalahan 3: Charset diletakkan di bawah script -->
  <meta charset="UTF-8">

  <!-- Kesalahan 4: CSS via @import di dalam inline style -->
  <style>
    @import url('/styles/theme.css'); /* Mematikan speculative parsing */
  </style>
</head>
<body>
  <!-- Kesalahan 5: Block element di dalam inline element yang salah diatur -->
  <span>
    <div>Konten Terfragmentasi</div>
  </span>

  <!-- Kesalahan 6: Malformed Tables -->
  <table>
    <div>Baris Data Tak Sah</div> <!-- Memicu Foster Parenting -->
  </table>
</body>
</html>
```

---

### 15. Production Best Practices & Linting/Standards (Standar Industri & Validasi)

1. **W3C Nu Html Checker**: Integrasikan engine `@html-validate/html-validate` atau `htmlhint` ke dalam alur *CI/CD pipeline* untuk memblokir kode yang melanggar spesifikasi.
2. **Aturan Linting Esensial**:
   - `doctype-first`: Memastikan `<!DOCTYPE html>` selalu menjadi baris pertama.
   - `attr-no-duplication`: Mencegah atribut ganda pada elemen tunggal yang dapat membingungkan query DOM.
   - `element-permitted-content`: Menolak penempatan anak di luar skema spesifikasi (misalnya elemen non-`<li>` sebagai anak langsung dari `<ul>`).
3. **Penyajian UTF-8**: Selalu konfigurasi HTTP response header web server (Nginx/Apache/Cloudflare) agar menyertakan:
   ```http
   Content-Type: text/html; charset=UTF-8
   ```
   Hal ini menjamin peramban menginisialisasi byte stream parser menggunakan mode encoding yang tepat tanpa sniffing lokal.

---

### 16. Real-World Failure Scenario & Debugging Case (Studi Kasus Kegagalan & Post-Mortem)

#### Insiden: Broken CSS Rendering & FCP Spike pada E-Commerce Checkout
- **Gejala**: Pengguna melaporkan bahwa tombol pembayaran tidak dapat diklik dan form berantakan hanya di peramban WebKit (Safari), sementara di Chromium (Chrome) tampilan terlihat normal. FCP melonjak dari 1.1s menjadi 4.8s.
- **Akar Masalah (Root Cause)**:
  Pengembang menyuntikkan template partial CMS untuk pelacakan marketing pihak ketiga tepat di atas `<!DOCTYPE html>`:
  ```html
  <!-- Tag pelacak terinjeksi tidak sengaja oleh skrip build -->
  <div><img src="tracking.pixel" /></div>
  <!DOCTYPE html>
  <html>
  ...
  ```
- **Dampak Engine**: Karena tag `<div>` muncul sebelum `<!DOCTYPE html>`, parser WebKit secara ketat menetapkan dokumen masuk ke dalam **Quirks Mode**. Dalam mode ini, Safari mengaplikasikan *quirks layout rules* lawas: elemen persentase tinggi (`height: 100%`) tidak dihitung dengan benar, meruntuhkan layout form checkout, sementara Speculative Scanner gagal mem-parsing resource header secara efisien.
- **Resolusi**:
  1. Membersihkan proses build injection agar payload analitik hanya disuntikkan di akhir `<body>`.
  2. Menambahkan langkah verifikasi automated test menggunakan headless Chromium dan WebKit dengan script deteksi:
     ```javascript
     if (document.compatMode !== 'CSS1Compat') {
       throw new Error('FATAL: Dokumen berjalan dalam Quirks Mode!');
     }
     ```

---

### 17. Verification & Testing Strategy (Strategi Verifikasi & Testing)

Gunakan suite tes otomatis (Playwright/Puppeteer) untuk memvalidasi kepatuhan parsing dan arsitektur dokumen:

```javascript
import { test, expect } from '@playwright/test';

test.describe('Verifikasi Integritas Arsitektur Dokumen HTML', () => {
  test('Dokumen harus beroperasi dalam Full Standards Mode', async ({ page }) => {
    await page.goto('/');
    
    // Verifikasi Quirks Mode tidak aktif (harus bernilai 'CSS1Compat', BUKAN 'BackCompat')
    const compatMode = await page.evaluate(() => document.compatMode);
    expect(compatMode).toBe('CSS1Compat');
  });

  test('Meta Charset harus dideklarasikan pada posisi pertama di head', async ({ page }) => {
    await page.goto('/');
    
    const isCharsetFirst = await page.evaluate(() => {
      const head = document.head;
      const firstChild = head.firstElementChild;
      return firstChild && firstChild.matches('meta[charset="UTF-8"]');
    });
    expect(isCharsetFirst).toBeTruthy();
  });

  test('Tidak ada Foster Parenting yang terpicu secara sembunyi-sembunyi', async ({ page }) => {
    await page.goto('/');
    
    // Mengecek apakah ada elemen yang tidak sengaja terdorong keluar dari tabel
    const orphanedElements = await page.evaluate(() => {
      const tables = document.querySelectorAll('table');
      let leaks = 0;
      tables.forEach(table => {
        // Cek jika sibling tepat sebelumnya adalah elemen terbuang
        const prev = table.previousElementSibling;
        if (prev && prev.classList.contains('fostered-content')) {
          leaks++;
        }
      });
      return leaks;
    });
    expect(orphanedElements).toBe(0);
  });
});
```

---

### 18. Cross-Platform/Browser Compatibility Matrix (Matriks Kompatibilitas)

| Fitur / Mekanisme | Blink (Chrome, Edge, Brave) | Gecko (Firefox) | WebKit (Safari, iOS Safari) | Dampak Kegagalan Standar |
| :--- | :--- | :--- | :--- | :--- |
| **HTML5 Parsing Specification** | 100% Sesuai Standard | 100% Sesuai Standard | 99% Sesuai Standard | Penyimpangan kecil pada penanganan *nested foreign content* (SVG/MathML). |
| **Preload Scanner (`<link rel="preload">`)** | Penuh | Penuh | Penuh (dengan batasan cache memory stream) | Request waterfall menjadi linier (lambat) jika preload scanner diabaikan. |
| **Automatic Doctype Quirks Fallback** | `BackCompat` diaktifkan instan jika karakter non-whitespace mendahului `DOCTYPE` | `BackCompat` diaktifkan | `BackCompat` diaktifkan | Model kalkulasi CSS box model beralih ke era IE5/Netscape. |
| **Script Attribute `defer` & `async`** | Penuh (Patuhi sequence spec) | Penuh | Penuh | Skrip non-defer memblokir total *main thread* hingga unduhan tuntas. |

---

### 19. Key Takeaways & Cheat Sheet (Rangkuman Eksekutif)

- Dokumen HTML diurai secara inkremental melalui pipeline: **Byte Stream $\to$ Unicode Characters $\to$ Tokens $\to$ Nodes $\to$ DOM Tree**.
- `<!DOCTYPE html>` adalah wajib dan non-negosiabel: tanpanya, dokumen dihitung sebagai broken markup dan peramban masuk ke dalam **Quirks Mode** (`document.compatMode === 'BackCompat'`).
- Deklarasi `<meta charset="UTF-8">` wajib muncul dalam **1024 byte pertama** berkas HTML guna mencegah restart parsing engine.
- Browser parser bersifat toleran terhadap error (*fail-safe*), namun algoritma koreksi seperti **Adoption Agency Algorithm** dan **Foster Parenting** membebani CPU renderer thread dan dapat merusak ekspektasi layout antarmuka.
- Aset skrip non-kritis harus selalu dideferensiasi menggunakan atribut `defer` atau `async` guna membebaskan konstruksi initial DOM tree dari kondisi parser blocking.

---

### 20. Challenge Exercises (Latihan Terpandu Mandiri)

#### Latihan 1: Forensik Quirks Mode
Buka website apa pun yang sedang Anda kembangkan menggunakan browser DevTools Console. 
1. Jalankan perintah `document.compatMode`.
2. Jika respons bernilai `"BackCompat"`, identifikasi karakter atau tag tersembunyi apa yang dicetak oleh server sebelum string `<!DOCTYPE html>`.
3. Perbaiki struktur dokumen hingga bernilai `"CSS1Compat"`.

#### Latihan 2: Membedah Foster Parenting
Tulis sepotong kode HTML dengan struktur tabel yang rusak: tempatkan tag `<p>` dan `<span>` tepat di antara tag `<table>` dan `<tr>`. 
1. Muat kode tersebut di browser.
2. Gunakan *Elements Inspector* di browser untuk melihat di mana letak sebenarnya dari tag `<p>` dan `<span>` tersebut dalam representasi DOM Tree final.
3. Jelaskan mengapa letak node tersebut berpindah dari lokasi deklarasi aslinya di file teks berdasarkan mekanisme *Foster Parenting*.

#### Latihan 3: Audit Preload Scanner
Uji performa sebuah file HTML yang memuat 3 file JavaScript eksternal berukuran masing-masing 1MB pada bagian `<head>`:
1. Skenario A: Menggunakan `<script src="...">` standar.
2. Skenario B: Menggunakan `<script src="..." defer>`.
3. Analisis bagan *Waterfall Network* pada DevTools untuk membedakan bagaimana *speculative parser* menangani pemuatan dokumen pada kedua skenario tersebut. Hitung selisih metrik FCP-nya.