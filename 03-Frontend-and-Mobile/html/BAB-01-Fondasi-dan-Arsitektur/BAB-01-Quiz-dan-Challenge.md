# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Arsitektur Web, Standar WHATWG, dan Parsing Engine**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **State Machine pada HTML5 Tokenizer**  
   Jelaskan secara mendalam bagaimana transisi status (*state transition*) berlangsung pada *HTML tokenizer* saat menemukan karakter `<`, `/`, nama *tag*, hingga penutup `>`. Mengapa HTML tokenizer tidak dapat diimplementasikan hanya dengan *regular expressions* berbasis Finite State Automata (FSA) standar?

2. **Dinamika Doktrin: Quirks Mode vs. Standards Mode**  
   Secara arsitektural, bagaimana browser engine (Blink/Gecko) menentukan mode rendering (*Quirks, Limited Quirks, Full Standards*) hanya dari pembacaan *prologue bytes* dokumen? Jelaskan konsekuensi komputasi pada *layout engine* (khususnya *box model calculation* dan pewarisan ukuran font) jika sebuah dokumen tidak memiliki `<!DOCTYPE html>`.

3. **Filosofi Toleransi: WHATWG Living Standard vs. W3C XML/XHTML DTD**  
   XML menerapkan prinsip *Draconian Error Handling* (fatal error saat *malformed syntax* terdeteksi), sementara WHATWG HTML5 secara eksplisit menolaknya dan mendefinisikan algoritma *error recovery* deterministik. Analisis alasan arsitektural di balik keputusan ini dari sudut pandang *backward compatibility*, stabilitas web terbuka, dan *fault tolerance*.

4. **In-Memory DOM Graph vs. Raw Byte Stream**  
   Jelaskan transformasi data dari *Network Layer* (TCP chunks / byte stream), *Character Decoding*, *Tokenization*, hingga *Tree Construction*. Mengapa operasi `element.innerHTML` pada dasarnya adalah proses serialisasi yang tidak selalu merefleksikan urutan byte asli yang dikirim oleh server?

5. **Interaksi Parser, CSSOM, dan Script Execution**  
   CSSOM tidak memblokir konstruksi HTML DOM secara langsung, namun sebuah tag `<script>` eksternal sinkron memblokir pembacaan HTML selanjutnya sampai CSSOM selesai di-*build*. Mengapa browser engine mengambil keputusan sinkronisasi ini? Jelaskan kondisi *deadlock* atau *race condition* yang dicegah oleh mekanisme tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Adoption Agency Algorithm (AAA)**  
   Ketika parser menemukan susunan markup yang salah bertingkat (*misnested tags*) seperti:
   ```html
   <p>Alpha <b>Beta <i>Gamma</p> Delta</i> Epsilon
   ```
   Bagaimana *Adoption Agency Algorithm* beroperasi menggunakan *List of Active Formatting Elements* dan *Stack of Open Elements* untuk menghasilkan DOM tree yang valid tanpa memicu *crash* pada parser?

2. **Preload Scanner (Speculative Parsing) & Batasan Deteksinya**  
   *Preload Scanner* berjalan secara asinkron di thread terpisah dari *Main Parsing Thread*. Uraikan bagaimana *speculative parser* membaca stream markup di depan *main tokenizer*, dan identifikasi minimal dua skenario arsitektural di mana *speculative parser* gagal (*blind spot*) mendeteksi dependensi kritis secara dini.

3. **Mekanisme Foster Parenting pada Parsing Konteks Tabular**  
   Pertimbangkan kode berikut:
   ```html
   <table>
     <div>Konten Ilegal</div>
     <tr><td>Valid Data</td></tr>
   </table>
   ```
   Jelaskan algoritma *Foster Parenting* yang dieksekusi oleh HTML parser. Di mana node `<div>` tersebut akan ditempatkan di dalam DOM tree akhir, dan apa rasionalitas di balik penempatan tersebut?

4. **Re-entrancy Risk & Parser Stalling via `document.write()`**  
   Mengapa penggunaan API warisan `document.write()` pada dokumen modern dianggap sebagai anti-pattern kritis yang merusak optimasi *token streaming*? Jelaskan bagaimana pemanggilan metode ini memaksa parser melakukan *insertion point manipulation* dan re-evaluasi *tokenizer state*.

5. **Streaming Chunk Boundaries pada HTTP/2 & HTTP/3**  
   Saat server mengirimkan respons HTML menggunakan `Transfer-Encoding: chunked` (atau HTTP/2 *DATA frames*) di mana batasan chunk memotong token di tengah jalan (misalnya chunk pertama berakhir pada `<div id="app` dan chunk kedua berlanjut dengan `"></div>`): Bagaimana tokenizer mempertahankan *internal state*-nya tanpa harus membatalkan atau mengulang pembacaan byte sebelumnya?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Hidrasi dan Parser-Blocking pada E-Commerce Monolith Skala Besar
Sebuah aplikasi e-commerce global menggunakan *HTML Streaming* dari Node.js server. Namun, metrik Core Web Vitals menunjukkan **First Contentful Paint (FCP)** dan **Largest Contentful Paint (LCP)** yang sangat lambat (degradasi >2.5 detik) di jaringan 4G/Mobile. Setelah dilakukan tracing via Chrome DevTools Performance Profiler, ditemukan visualisasi *Main Thread* mengalami celah kosong (*gap*) panjang di tengah proses pembacaan HTML, bertepatan dengan sebuah script tag analitik pihak ketiga di bagian `<head>`:

```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="/styles/critical.css">
  <script src="https://cdn.thirdparty-tracker.com/bundle.js"></script>
  <script src="/scripts/app.js" defer></script>
</head>
<body>
  <!-- Konten LCP Hero Image di-stream di sini -->
```

* **Pertanyaan Diagnostik:**
  1. Bedah secara mekanistis rantai pemblokiran yang terjadi: Mengapa keberadaan script pihak ketiga tersebut menahan render tree dan streaming token HTML body, meskipun `/styles/critical.css` telah dimuat?
  2. Solusi arsitektur apa yang harus diimplementasikan tanpa menghapus fungsionalitas analitik tersebut? Jelaskan perbandingan evaluasi teknis antara penambahan atribut `async`, `defer`, pemindahan tag, hingga penggunaan Web Worker (via Partytown/OffscreenCanvas).

---

### Skenario B: DOM Clobbering & Hierarchy Mutation pada Web Components
Sebuah platform perbankan menggunakan pendekatan arsitektur *micro-frontend* berbasis Web Components. Beberapa tim menggunakan manipulasi *direct DOM* dengan menyuntikkan template dinamis via `container.innerHTML = payload`. Suatu hari, sistem otorisasi transaksi mengalami kegagalan fungsi (*bypass condition*) karena script inti gagal membaca referensi API bawaan akibat insiden DOM Clobbering. Struktur yang disuntikkan secara dinamis memiliki pola:

```html
<form id="authConfig">
  <input name="endpoint" value="/api/v1/auth">
</form>
```

Pada kode aplikasi global:
```javascript
const target = window.authConfig.endpoint.value || "/default/api";
fetch(target, { method: "POST" });
```

* **Pertanyaan Diagnostik:**
  1. Bagaimana HTML parsing engine memetakan atribut `id` dan `name` ke dalam global namespace `window` (*Named Access on the Window Object*) sesuai spesifikasi WHATWG?
  2. Mengapa modifikasi struktur DOM melalui *string injection* tanpa melalui *HTML Sanitizer API* atau *DOMParser context* dapat merusak integritas eksekusi JavaScript yang mengandalkan global scope?
  3. Berikan mitigasi teknis mutlak pada level arsitektur kode aplikasi dan konfigurasi *Content Security Policy (CSP)* untuk menetralkan eksploitasi parsing ini.

---

### Skenario C: Trade-off Arsitektural Edge-SSR: Immediate Flush vs. Dynamic Metadata
Tim infrastruktur merancang arsitektur baru menggunakan Cloudflare Workers untuk melakukan *Edge-SSR*. Terdapat perdebatan teknis antara dua Senior Staff Engineer:
* **Engineer A** mengusulkan untuk melakukan *immediate flush* dari `<head>` dan *skeleton layout* segera setelah koneksi dibuka (chunk 0), sebelum database query selesai, agar browser dapat langsung mengunduh CSS, font, dan menjalankan *speculative parser*.
* **Engineer B** menolak usulan tersebut karena aplikasi memerlukan data dari database query untuk mengisi metadata dinamis pada `<head>` (seperti `<title>`, `<meta property="og:*">`, dan *nonce* dinamis untuk CSP `script-src 'nonce-...'`).

* **Pertanyaan Diagnostik:**
  1. Analisis *trade-off* performa vs. fungsionalitas/keamanan dari kedua pendekatan ini. Metrik browser apa saja yang diuntungkan oleh strategi Engineer A, dan risiko apa yang dihadapi Engineer B?
  2. Apakah mungkin menggabungkan *immediate flush* untuk aset statis sambil tetap mempertahankan integrasi *CSP Nonce* yang aman dan metadata SEO yang dinamis? Rancang solusi arsitektural konkret menggunakan standar HTML Streaming dan mekanisme *Edge HTML Rewriter*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Engine Diagnostic — Mengimplementasikan Deterministic Token Transformer & Adoption Agency Simulator

#### Problem Statement
Dalam proses pembuatan engine rendering minimalis internal, Anda ditugaskan untuk membangun parser layer berbasis spesifikasi WHATWG subset sederhana. Parser ini harus mampu membaca stream token dan menghasilkan representasi struktur JSON Tree yang merefleksikan penanganan tag bersarang abnormal (*misnested tags*) dan *error recovery* tanpa bergantung pada engine bawaan browser.

#### Functional Requirements
1. **Token Ingestion**: Implementasikan fungsi `parseTokenStream(tokens)` yang menerima array objek token:
   ```typescript
   type Token = 
     | { type: 'StartTag'; name: string }
     | { type: 'EndTag'; name: string }
     | { type: 'Character'; data: string };
   ```
2. **Deterministic Tree Building**: Parser harus mempertahankan dua data structure utama:
   * *Stack of Open Elements*
   * *List of Active Formatting Elements* (khusus formatting tags: `b`, `i`, `u`, `span`)
3. **Adoption Agency Emulation**: Ketika menerima token `EndTag` untuk sebuah formatting element yang bukan merupakan *top of the stack of open elements*, parser tidak boleh langsung membuang tag tersebut. Parser harus merekonstruksi hierarchy (cloning formatting context) sesuai prinsip algoritma WHATWG AAA dasar.
4. **Foster Parenting**: Jika karakter atau token inline ditemukan di dalam konteks token konteks `table` di luar `td`/`th`/`tr`, node tersebut harus "dilempar" (*foster-parented*) menjadi sibling sebelum node `table`.

#### Technical Constraints
* **Pure Logic**: Larangan total menggunakan library pihak ketiga (`jsdom`, `cheerio`, `htmlparser2`) atau memanfaatkan engine host (`document.createElement`, `DOMParser`).
* **Runtime**: Kode harus dapat dieksekusi secara deterministik pada environment Node.js 18+ (ESM).
* **Kompleksitas**: Waktu eksekusi parsing untuk $N$ token harus beroperasi pada batas $O(N)$ amortized.

#### Expected Output
Input token stream dari markup:
`<b>1<i>2</b>3</i>`

Harus menghasilkan struktur JSON tree deterministik:
```json
{
  "nodeName": "root",
  "children": [
    {
      "nodeName": "b",
      "children": [
        { "nodeName": "#text", "value": "1" },
        {
          "nodeName": "i",
          "children": [{ "nodeName": "#text", "value": "2" }]
        }
      ]
    },
    {
      "nodeName": "i",
      "children": [{ "nodeName": "#text", "value": "3" }]
    }
  ]
}
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Model kerja matematika *HTML Tokenizer* sebagai *State Machine* dan perbedaannya dengan *Context-Free Grammar (CFG)* parser.
- [ ] Alasan spesifik mengapa HTML tidak bisa diparsing menggunakan parser LL(k) atau LR(k) standar tanpa campur tangan state feedback dari Tree Constructor.
- [ ] Peran dan fungsionalitas *Stack of Open Elements* serta *List of Active Formatting Elements*.
- [ ] Mekanisme internal browser dalam mengisolasi *tokenization* pada main thread dan *lookahead operations* pada speculative thread.
- [ ] Alur hidup *Critical Rendering Path* dari byte TCP hingga terbentuknya layout frame pertama.
- [ ] Implikasi hukum keamanan dari *Named Access on Window* dan mekanisme perlindungan terhadap serangan berbasis *DOM Clobbering*.

### Saya tidak perlu menghafal:
- [ ] 80+ state spesifik di dalam diagram alur formal WHATWG Tokenization State Machine (cukup memahami pola transisi status utamanya).
- [ ] Daftar lengkap *legacy system identifiers* yang memicu peralihan ke *Quirks Mode*.
- [ ] Detail algoritma *Adoption Agency* secara byte-per-byte (cukup memahami logika 8 langkah teoretis: pencarian formatting element, furthest block, reparenting, dan pointer swap).

### Saya harus bisa melakukan:
- [ ] Membaca trace Chromium Performance Profiler untuk mengidentifikasi parser-blocking assets dan long task akibat layout thrashing saat proses konstruksi DOM berlangsung.
- [ ] Mengonfigurasi arsitektur penyajian HTML (Edge-SSR/Node Stream) dengan peletakan deklarasi aset (`preload`, `modulepreload`, `defer`, `async`) yang memaksimalkan utilisasi *Preload Scanner*.
- [ ] Mendiagnosis dan memperbaiki *rendering artifact* (seperti FOUC — *Flash of Unstyled Content*) yang disebabkan oleh parsing interupsi script sinkron.
- [ ] Mengaudit markup berbahaya yang memanfaatkan celah parsing recovery untuk melakukan manipulasi DOM atau bypass proteksi keamanan client-side.