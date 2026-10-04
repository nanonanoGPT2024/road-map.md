# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Text-Level Semantics, Tipografi Teknis, dan Lokalisasi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Arsitektur Internal Browser Engine**: Memahami siklus hidup rendering elemen *text-level semantics* dari parsing HTML, pembuatan *DOM node*, *Inline Formatting Context* (IFC), *glyph shaping* melalui pustaka native (HarfBuzz/DirectWrite/CoreText), hingga sinkronisasi dengan *Accessibility Tree* (AXTree).
- **Mengimplementasikan Isolasi Bidirectional (BiDi) Berskala Enterprise**: Memitigasi kerentanan *BiDi bleed* pada platform multi-bahasa global menggunakan `<bdi>`, `<bdo>`, dan algoritma Unicode Bidirectional Algorithm (UBA / UAX #9) tanpa merusak integritas data visual maupun logikal.
- **Merekayasa Metadata Temporal dan Numerik Machine-Actionable**: Mengintegrasikan elemen `<time>` (ISO 8601, durasi temporal, zona waktu global) dan `<data>` ke dalam *pipeline microdata* dan indexing AI/search engine.
- **Mengembangkan Tipografi Teknis Presisi Tinggi**: Menyusun dokumentasi teknis sistemik interaktif dengan semantik `<code>`, `<kbd>`, `<samp>`, dan `<var>` yang terisolasi dan *accessible* secara programatik.
- **Merancang Anotasi Fonetik Lintas Skrip (East Asian Typography)**: Mengimplementasikan elemen `<ruby>`, `<rt>`, dan `<rp>` untuk *script fallback* dan anotasi *furigana/pinyin* pada sistem enterprise berstandar CJK (*Chinese, Japanese, Korean*).
- **Mengevaluasi Trade-off Kinerja Rendering Teks**: Mengoptimalkan reflow DOM, meminimalkan biaya rekonstruksi *text runs*, dan mengeliminasi latensi *layout thrashing* pada aplikasi dengan throughput data dinamis tinggi.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **DOM & Render Tree Fundamentals**: Siklus hidup rendering browser (Parsing -> DOM -> CSSOM -> Layout/Reflow -> Paint -> Composite).
- **Karakter Enkoding & Unicode Basics**: Pemahaman mengenai UTF-8, code points, grapheme clusters, dan byte order.
- **CSS Formatting Contexts**: Mekanisme kerja Block Formatting Context (BFC) dan Inline Formatting Context (IFC).
- **A11y Core Principles**: Dasar-dasar Accessible Rich Internet Applications (WAI-ARIA) dan cara kerja *Screen Reader* membaca dokumen web.

---

## 3. Concept & Internal Architecture

Implementasi semantik level teks bukan sekadar penataan tampilan visual, melainkan instruksi langsung ke inti engine browser (Blink, Gecko, WebKit) yang mengatur pembentukan token logikal, layouting glif teks, dan pemetaan ke *Accessibility API* sistem operasi.

```
       Raw HTML Stream
              │
              ▼
   [HTML Tokenizer & Tree Builder]
              │
              ▼
         [DOM Tree] ───────────────┐
              │                    │
              ▼                    ▼
     [Style Computation]     [AXObjectCache]
              │                    │
              ▼                    ▼
     [Layout Engine (IFC)]     [AXTree / Assistive Tech]
              │              (Screen Readers, Braille)
              ▼
    [Text Run Segmentation]
     - Script Run Splitting
     - BiDi Resolution (UAX #9)
     - Font Selection
              │
              ▼
  [Glyph Shaping (HarfBuzz)]
              │
              ▼
    [Rasterization & Paint]
```

### 3.1. Parsing, IFC, dan Text Runs
Ketika parser mendeteksi elemen inline seperti `<code>`, `<time>`, atau `<bdi>`, browser tidak membentuk boundary blok baru. Elemen-elemen ini hidup di dalam **Inline Formatting Context (IFC)**:
1. **Line Breaking & Text Runs**: Browser memecah teks menjadi fragmen-fragmen kecil yang disebut *text runs*. Jika parser menemukan tag semantik inline, browser membuat `LayoutInline` object yang membungkus satu atau beberapa `LayoutText` runs.
2. **Font Selection & Glyph Shaping**: Engine teks (misal: HarfBuzz pada Chromium/Android/Linux) memetakan urutan *Unicode code points* ke *glyph ID* spesifik pada font yang digunakan. Elemen seperti `<code>` memicu pemilihan font berbobot monospace secara default melalui *user-agent stylesheet*, yang mengubah kalkulasi *advance width* secara seragam.
3. **Soft Wrap Opportunity (`<wbr>`)**: Karakter biasa dipecah berdasarkan spasi atau aturan kamus bahasa (*hyphenation dictionary*). Kehadiran `<wbr>` menyuntikkan *zero-width break opportunity* di tingkat parser layout, menginstruksikan engine bahwa pemecahan baris diizinkan pada koordinat tersebut tanpa merender tanda hubung (*hyphen*), berguna untuk string panjang seperti SHA-256 hash atau URL API.

### 3.2. Unicode Bidirectional Algorithm (UBA / UAX #9) dan Isolasi DOM
Teks dalam web dapat mengalir Left-to-Right (LTR - misal: Latin, Sirilik) atau Right-to-Left (RTL - misal: Arab, Ibrani). Algoritma UBA menyelesaikan arah visual berdasarkan level keterarahan karakter (tipe *Strong*, *Weak*, atau *Neutral*).

- **Masalah BiDi Bleed**: Ketika teks LTR disisipkan langsung ke dalam teks RTL (atau sebaliknya) tanpa batas isolasi, karakter netral (seperti tanda baca `!`, `/`, `-`, tanda kurung, atau angka) di sekitar batas akan "terserot" ke arah aliran konteks induknya.
- **`<bdi>` (Bidirectional Isolate)**: Secara internal, engine browser menetapkan CSS `unicode-bidi: isolate` pada elemen ini. Node layout engine mengunci arah teks di dalam elemen tersebut menggunakan *directional isolate controls* (mirip dengan menyisipkan karakter Unicode `U+2066` / `U+2067` dan ditutup `U+2069`). Karakter netral di luar node `<bdi>` tidak akan terpengaruh oleh karakter kuat di dalam `<bdi>`.
- **`<bdo>` (Bidirectional Override)**: Menetapkan CSS `unicode-bidi: bidi-override`. Engine mengabaikan atribut direksional bawaan karakter Unicode dan secara paksa merender urutan visual glif strictly sesuai atribut `dir="ltr"` atau `dir="rtl"`.

### 3.3. Pipeline Aksesibilitas (AXTree Mapping)
Browser memetakan elemen semantik teks ke peran (*roles*), atribut (*states*), dan properti platform native (seperti NSAccessibility di macOS, UI Automation di Windows, ATK/AT-SPI di Linux):
- `<time datetime="...">`: Menetapkan semantik tanggal/waktu yang valid ke node AX, memungkinkan asisten virtual atau pembaca layar mengumumkan durasi atau tanggal absolut yang telah dinormalisasi tanpa terdistorsi oleh format tipografi visual (misal: "2d ago").
- `<abbr title="...">`: Mendaftarkan asosiasi ekspansi teks ke dalam tree. Engine mempertahankan referensi nama aksara utuh untuk dibaca saat kursor melakukan hover atau saat pembaca layar beralih ke mode pengucapan detail.
- `<del>` dan `<ins>`: Menghasilkan role `deletion` dan `insertion`. Screen reader kelas enterprise akan mengumumkan: *"Mulai teks yang dihapus"* dan *"Akhir teks yang dihapus"*, bukan sekadar membaca teks polos.
- `<ruby>`, `<rt>`, `<rp>`: Mengaktifkan CSS Ruby Model. Komponen layout membagi teks menjadi *ruby base box* dan *ruby annotation box*. Parser menyembunyikan tag `<rp>` (Ruby Fallback Parenthesis) jika engine mendukung visualisasi dua dimensi, namun `<rp>` tetap tersedia di stream linear untuk fallback rendering pada engine berbasis teks terminal atau browser tanpa dukungan CSS Ruby.

---

## 4. Why & What

| Tag Semantik | Kategori Semantik | Perilaku Default Browser Engine | Dampak Terhadap A11y & Parsing Mesin |
| :--- | :--- | :--- | :--- |
| `<code>` | Tipografi Teknis | `font-family: monospace` (IFC) | Memetakan ke role generic/code; mematikan typographical smart quotes. |
| `<kbd>` | Tipografi Teknis | `font-family: monospace` (IFC) | Diekspos sebagai masukan keyboard pengguna; assistive tech mengenali interaksi fisik. |
| `<samp>` | Tipografi Teknis | `font-family: monospace` (IFC) | Menandakan output langsung dari eksekusi sistem/program. |
| `<var>` | Tipografi Teknis | `font-style: italic` (IFC) | Menandakan variabel matematika atau variabel referensi dalam rekayasa perangkat lunak. |
| `<time>` | Metadata Temporal | Inline text rendering | Mengikat string mesin terstruktur ISO 8601 ke teks representasi visual. |
| `<data>` | Metadata Numerik | Inline text rendering | Mengikat data numerik/ID internal (`value`) ke representasi antarmuka. |
| `<bdi>` | Lokalisasi (I18N) | `unicode-bidi: isolate` | Mengisolasi kalkulasi directional run UBA dari container induk. |
| `<bdo>` | Lokalisasi (I18N) | `unicode-bidi: isolate-override` | Memaksa urutan render glif secara deterministik mengabaikan UAX #9. |
| `<ruby>`, `<rt>` | East-Asian A11y | CSS Ruby Display Formatting | Merender anotasi mikro fonetik/semantik di atas atau di samping glif dasar. |
| `<rp>` | East-Asian Fallback | `display: none` (jika engine support ruby) | Memberikan delimitasi tanda kurung `()` jika browser gagal menguraikan ruby layout. |
| `<wbr>` | Flow Control | Zero-width line-break opportunity | Titik pemotongan kata tanpa injeksi tanda hubung visual pada layouting panjang. |
| `<abbr>` | Semantik Leksikal | Inline text rendering | Menghubungkan akronim/singkatan ke pelafalan penuh via atribut `title`. |

### Mengapa Pendekatan Enterprise Menolak `<span>` Berlebihan (*Div Soup / Spanitis*)?
1. **Machine Understandability & SEO Semantik**: Bot pengindeks web modern mengekstrak relasi semantik. Penggunaan elemen `<time datetime="...">` secara langsung mengizinkan Google Knowledge Graph, indeks event, dan indexing kalender mengurai metadata tanpa *heuristic parsing* yang rentan galat.
2. **Defensive Bidirectionality**: Dalam platform multi-tenant (SaaS global), input pengguna bersifat tidak tepercaya (*untrusted user input*). Jika pengguna asal Arab memasukkan nama produk yang bercampur alfabet Latin dan angka, ketiadaan `<bdi>` dapat merusak layout tabel finansial seluruh baris antarmuka.
3. **Integritas Assistive Technology**: Tunanetra yang mengoperasikan terminal web bergantung pada pelafalan `<kbd>` untuk kombinasi shortcut, serta parsing `<del>` dan `<ins>` untuk melacak review dokumen hukum/finansial secara realtime.

---

## 5. How (Workflow Detail)

Untuk menerapkan text-level semantics dan tipografi teknis pada skala enterprise, ikuti pipeline berikut:

```
[Untrusted/External Data Input]
               │
               ▼
[Step 1: Ingestion & Normalization]
  - Validasi Skrip Unicode (LTR / RTL)
  - Parsing String Waktu ke Standar Temporal ISO 8601
               │
               ▼
[Step 2: Semantic Tokenization]
  - Bungkus User Generated String dengan <bdi>
  - Ekstrak Data Teknis -> <code>, <kbd>, <samp>, <var>
  - Format Waktu Relatif -> <time datetime="ISO_8601">
               │
               ▼
[Step 3: Tipografi Kompleks & Script Annotation]
  - Jika Teks Berkarakter Kanji/Hanja -> Injeksi <ruby><rt><rp>
  - Jika String Monolitik (Token, Hash, Path) -> Injeksi <wbr> pada Break Boundary
               │
               ▼
[Step 4: Layout & Font Stack Orchestration]
  - Terapkan CSS unicode-range & CSS font-variant-numeric: tabular-nums
  - Fallback check untuk CSS Ruby dan Directional Isolation
               │
               ▼
[Step 5: Accessibility Auditing]
  - AXTree Inspection (Memastikan role terdaftar dan tidak redundant)
```

### Langkah 1: Parsing dan Normalisasi Temporal di Edge / Backend
Waktu visual tidak boleh dikirim dalam format relatif mentah tanpa jangkar mesin. Backend atau Web Component harus selalu memproduksi format ISO 8601 yang valid (`YYYY-MM-DD`, `YYYY-MM-DDThh:mm:ssTZD`, atau format durasi `PnYnMnDTnHnMnS`).

### Langkah 2: Konstruksi Bidirectional Isolate Boundary
Setiap rendering nama entitas pengguna (username, nama organisasi, nomor referensi mutasi) yang diinjeksi ke dalam antarmuka LTR/RTL wajib dibungkus secara mutlak di dalam elemen `<bdi>`:
```html
<!-- Mengamankan context pembacaan: Nama Arab di dalam UI Bahasa Inggris -->
<p>User <bdi lang="ar">فاطمة</bdi> updated the deployment status.</p>
```

### Langkah 3: Segmentasi Tipografi Monospace Presisi
Saat merender log audit atau instruksi CLI:
- Input pengguna dibungkus `<kbd>`.
- Token variabel sistem dinamis dibungkus `<var>`.
- Respon sistem operasi/backend mentah dibungkus `<samp>`.
- Cuplikan program internal dibungkus `<code>`.

---

## 6. Analogy & Diagram ASCII

### Analogi Kontainer Kargo Kedap Udara (Isolasi BiDi)
Bayangkan layout halaman adalah sebuah kapal kargo yang berlayar dari barat ke timur (LTR). 
- Jika Anda memasukkan muatan cair bertekanan tinggi (teks RTL) tanpa kontainer khusus ke dek kapal, cairan tersebut akan tumpah dan membanjiri ruang di sekitarnya, mengubah titik pusat gravitasi kapal (tanda baca terbalik, angka berpindah sisi).
- Elemen `<bdi>` bertindak seperti **kontainer bertekanan kedap udara**. Apapun gejolak arah fluida di dalam kontainer, sistem eksterior kapal tetap stabil bergerak dari barat ke timur tanpa terganggu oleh medan gaya fluida di dalamnya.

```
Layout LTR Konteks Induk:
─────────────────────────────────────────────────────────────────────────────
Order Logikal:  "User "  +  [ ARABIC_STRING ]  +  " commented on ticket #42"
─────────────────────────────────────────────────────────────────────────────

TANPA <bdi> (BiDi Bleed Hazard):
  Visual Render: User 42# teckit no detnemmoc [GNIRTS_CIBARA]
  (Tanda # dan angka 42 terbalik arah bacanya karena ditarik oleh script RTL)

DENGAN <bdi> (Isolated Formatting Context):
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ User <bdi>[GNIRTS_CIBARA]</bdi> commented on ticket #42                 │
  └─────────────────────────────────────────────────────────────────────────┘
  (Batas isolasi mencegah medan RTL bocor ke teks LTR di sekitarnya)
```

### Diagram Layout Rendering Elemen Ruby (Tipografi CJK)
```
  Visual Display:
         とう    きょう              <- <rt> (Ruby Text Box: Anotasi Fonetik)
        ┌────┐  ┌────┐
        │ 東 │  │ 京 │              <- Base Text (Kanji Glyphs)
        └────┘  └────┘
  
  DOM Stream Fallback (Non-Ruby Engine):
  東<rp>(</rp><rt>とう</rt><rp>)</rp>京<rp>(</rp><rt>きょう</rt><rp>)</rp>
  Output Text-Only Browser: 東(とう)京(きょう)
```

---

## 7. Simple Example & Practical Example

### Simple Example: Dokumen Semantik Standar
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Audit Eksekusi Sistem</title>
</head>
<body>
  <article>
    <p>
      Eksekusi pembaruan dilakukan oleh <bdi>أحمد</bdi> pada 
      <time datetime="2023-10-24T14:32:00Z">24 Oktober 2023 pukul 14:32 UTC</time>.
    </p>
    <p>
      Tekan <kbd><kbd>Ctrl</kbd> + <kbd>C</kbd></kbd> untuk menghentikan loop perintah 
      <code>kill -9 <var>pid</var></code>.
    </p>
    <p>
      Respon server: <samp>502 Bad Gateway: Connection to node-cluster-04 terminated.</samp>
    </p>
  </article>
</body>
</html>
```

### Practical Example: Enterprise Audit Log & Localization Engine Component
Berikut adalah implementasi komponen antarmuka log audit finansial tingkat produksi yang menangani multi-skrip, bidirectional rendering, presisi waktu mikrodetik, dan anotasi tipografi legal:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Security & Transaction Audit Console</title>
  <style>
    :root {
      --font-mono: "JetBrains Mono", "Fira Code", monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --color-bg: #0f172a;
      --color-surface: #1e293b;
      --color-border: #334155;
      --color-text: #f8fafc;
      --color-text-muted: #94a3b8;
      --color-accent: #38bdf8;
      --color-danger: #f87171;
      --color-success: #4ade80;
    }

    body {
      font-family: var(--font-sans);
      background-color: var(--color-bg);
      color: var(--color-text);
      padding: 2rem;
      line-height: 1.5;
    }

    .audit-table {
      width: 100%;
      border-collapse: collapse;
      background-color: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: 8px;
      overflow: hidden;
      font-variant-numeric: tabular-nums;
    }

    .audit-table th, 
    .audit-table td {
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--color-border);
      text-align: left;
      vertical-align: middle;
    }

    .audit-table th {
      background-color: #111827;
      font-weight: 600;
      color: var(--color-text-muted);
      text-transform: uppercase;
      font-size: 0.75rem;
      letter-spacing: 0.05em;
    }

    /* Tipografi Teknis Lanjutan */
    code, samp, kbd, var {
      font-family: var(--font-mono);
      font-size: 0.85em;
    }

    code {
      background-color: rgba(56, 189, 248, 0.1);
      color: var(--color-accent);
      padding: 0.15em 0.4em;
      border-radius: 4px;
    }

    kbd {
      background-color: #334155;
      color: #f8fafc;
      border: 1px solid #475569;
      border-bottom-width: 2px;
      padding: 0.1em 0.35em;
      border-radius: 3px;
      box-shadow: 0 1px 1px rgba(0,0,0,0.2);
      white-space: nowrap;
    }

    samp {
      color: #cbd5e1;
      background: #090d16;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      display: inline-block;
      max-width: 280px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    var {
      color: #fbbf24;
      font-style: normal;
    }

    /* East Asian Ruby Typography Styling */
    ruby {
      ruby-position: over;
      font-size: 1rem;
    }

    rt {
      font-size: 0.65em;
      color: var(--color-text-muted);
      letter-spacing: 0;
      user-select: none;
    }

    .hash-token {
      word-break: break-all;
      color: var(--color-text-muted);
    }
  </style>
</head>
<body>

  <main>
    <h1>Global Transaction & Audit Trail</h1>
    
    <table class="audit-table">
      <thead>
        <tr>
          <th>Transaction Ref / ID</th>
          <th>Actor (Global Multi-tenant)</th>
          <th>Timestamp (Normalized)</th>
          <th>Action Payload & Telemetry</th>
          <th>Value Index</th>
        </tr>
      </thead>
      <tbody>
        <!-- Skenario 1: Input Pengguna Arab (RTL) di UI English (LTR) -->
        <tr>
          <td>
            <code class="hash-token">0x9a8b<wbr>c4d2<wbr>e8f0<wbr>11ec<wbr>b9dd</code>
          </td>
          <td>
            <!-- Isolasi mutlak untuk mencegah directional bleed -->
            <bdi lang="ar" dir="rtl">طارق بن زياد</bdi>
            <span style="color: var(--color-text-muted); font-size: 0.8em;">(ID: #8849)</span>
          </td>
          <td>
            <time datetime="2023-11-15T08:30:45.123+03:00">
              Nov 15, 2023, 08:30:45 AST
            </time>
          </td>
          <td>
            User invoked execution: <code>deploy --target=<var>cluster_node_eu</var></code>
          </td>
          <td>
            <data value="1500000.00">$1,500,000.00</data>
          </td>
        </tr>

        <!-- Skenario 2: Anotasi Fonetik Pasar Asia (CJK) -->
        <tr>
          <td>
            <code class="hash-token">0x7f3a<wbr>11c9<wbr>d4e2<wbr>44bb<wbr>a012</code>
          </td>
          <td>
            <!-- Ruby annotations untuk ketepatan legal pelafalan nama korporat -->
            <ruby>
              新<rp>(</rp><rt>しん</rt><rp>)</rp>
              日<rp>(</rp><rt>にっ</rt><rp>)</rp>
              本<rp>(</rp><rt>ぽん</rt><rp>)</rp>
            </ruby> Holdings Corp.
          </td>
          <td>
            <time datetime="2023-11-15T05:31:10.004Z">
              Nov 15, 2023, 05:31:10 UTC
            </time>
          </td>
          <td>
            Terminal output: <samp>STATUS_OK: ACK received via socket 127.0.0.1</samp>
          </td>
          <td>
            <data value="84000000">&yen;84,000,000</data>
          </td>
        </tr>

        <!-- Skenario 3: Modifikasi Legal Audit & Override Arah Teks Khusus -->
        <tr>
          <td>
            <code class="hash-token">0x33e1<wbr>88bc<wbr>f5a1<wbr>10ee<wbr>99ab</code>
          </td>
          <td>
            <bdi lang="he">יוסי כהן</bdi>
          </td>
          <td>
            <time datetime="P0Y0M0DT2H15M0S">
              Durasi Sesi: 2h 15m
            </time>
          </td>
          <td>
            Revisi klausul: 
            <del style="color: var(--color-danger);">fee = 0.05%</del> 
            <ins style="color: var(--color-success); text-decoration: none; border-bottom: 1px dashed;">fee = 0.02%</ins>
            (Shortcut: <kbd><kbd>Alt</kbd> + <kbd>Enter</kbd></kbd>)
          </td>
          <td>
            <!-- Paksa arah baca ID Serial Part tertentu terlepas karakter alfabet -->
            <bdo dir="ltr">SER-9988-X</bdo>
          </td>
        </tr>
      </tbody>
    </table>
  </main>

</body>
</html>
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Frontend High-Frequency Forex Trading & Telemetry Engine (GlobalFX)
Pada platform trading valuta asing enterprise GlobalFX, terdapat antarmuka web interaktif yang menampilkan *streaming tick data* (hingga 50 transaksi per detik), chat room trader lintas negara (campuran Inggris, Arab, Hebrew, Jepang), dan visualisasi log intervensi sistem.

### Masalah Arsitektur Skala Produksi:
1. **BiDi Crash & Layout Breaking**: Nama trader Arab atau Israel sering mengandung nomor akun dalam tanda kurung atau ticker pasangan mata uang (misal: `USD/ILS`). Tanpa isolasi semantik, percampuran teks LTR dan RTL menyebabkan angka floating profit `+12.4%` bergeser posisi menjadi `%12.4+`, menimbulkan interpretasi fatal bagi trader.
2. **Reflow Thrashing Akibat Pembaruan Waktu**: Setiap baris tabel order memiliki durasi floating (misal: "berjalan 4 menit"). Pembaruan berbasis teks polos non-semantik memicu layout thrashing di level DOM karena browser engine tidak dapat mengoptimalkan parsing boundary text runs.
3. **Screen Reader Failure**: Trader dengan keterbatasan penglihatan (*visually impaired*) yang memantau eksekusi order melalui VoiceOver atau NVDA mendengar: *"Zero point zero two slash five"* bukan representasi semantik rasio atau singkatan finansial standar.

### Solusi Arsitektur:
1. **Enkapsulasi Batas BiDi**: Seluruh nama dan input trader di-serialize ke dalam virtual DOM / template engine dengan tag wajib `<bdi>`. Simbol pasangan mata uang dibungkus `<bdo dir="ltr">` untuk menjamin separator garis miring (`/`) selalu diproses dari kiri ke kanan terlepas dari locale antarmuka pengguna.
2. **Standardisasi Microdata Temporal**: Menggunakan elemen `<time datetime="ISO_STRING">` yang nilainya diperbarui melalui manipulasi atribut `dateTime` secara langsung, bukan me-render ulang seluruh innerHTML text node. Engine accessibility menggunakan string mesin tersebut untuk konversi audio yang akurat.
3. **Fragmentasi Hash Transaksi Zero-Reflow**: Penggunaan `<wbr>` yang ditempatkan secara terprogram setiap 4 atau 8 karakter pada ID transaksi panjang, mencegah meledaknya lebar tabel (*table cell blowup*) tanpa memaksakan CSS `word-break: break-all` yang dapat merusak penyalinan teks (*copy-paste experience*).

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan (Pros) | Biaya & Kompromi (Cons) | Rekomendasi Mitigasi |
| :--- | :--- | :--- | :--- |
| **Elemen `<bdi>` pada Setiap Input Dinamis** | Menjamin 100% isolasi Unicode; mencegah BiDi layout corruption secara permanen. | Sedikit peningkatan ukuran memori DOM Tree (overhead object pointer C++ pada Blink/WebKit). | Terapkan secara selektif pada dynamic user inputs, username, and international free-text fields. |
| **Pustaka CSS Monospace Khusus untuk `<code>`, `<samp>`** | Visualisasi data teknis presisi tinggi, meminimalisir kesalahan pembacaan karakter ambigu (`0` vs `O`, `l` vs `1`). | Ukuran transfer font woff2 bertambah (~30KB-80KB); potensi FOIT/FOUT. | Gunakan `font-display: swap` dan subset glif hanya untuk rentang Unicode dasar dan simbol teknis. |
| **Elemen `<ruby>` untuk Teks Multibahasa** | Pemenuhan regulasi tipografi East Asian typography; kejelasan nama legal. | Meningkatkan kerumitan kalkulasi line-height pada Inline Formatting Context (IFC). | Tetapkan CSS line-height yang cukup (misal: `line-height: 2`) pada container yang memuat ruby untuk mencegah clipping. |
| **Elemen `<time datetime="...">` Lengkap** | Kompatibel dengan indexing mesin pencari, web scraper cerdas, dan accessibility APIs. | Serialisasi tanggal backend ke ISO-8601 di edge memakan siklus CPU mikro. | Lakukan parsing tanggal sekali di level transform layer (API Gateway/BFF), bukan di render loop klien. |

---

## 10. Common Mistakes & Troubleshooting

### Tabel Diagnostik Masalah Produksi

| Gejala Bug / Isu | Akar Masalah (Root Cause) | Solusi Perbaikan (Fix) |
| :--- | :--- | :--- |
| Tanda kurung atau tanda seru meloncat ke sisi berlawanan pada nama user Arab/Ibrani. | **BiDi Bleed**: Karakter netral dievaluasi mengikuti arah skrip terdekat tanpa isolasi level token. | Bungkus nilai variabel string dengan `<bdi lang="...">...</bdi>`. Hindari hanya menggunakan tag visual `<span>`. |
| Screen reader membacakan "P-1-Y-2-M" alih-alih durasi waktu manusiawi. | Sintaks atribut `datetime` durasi tidak valid atau tidak memiliki teks fallback visual. | Gunakan format baku ISO 8601 Duration: `<time datetime="P1Y2M">1 tahun 2 bulan</time>`. |
| Teks ruby bertumpuk atau memotong baris teks di atasnya pada Firefox/Safari. | Nilai `line-height` pada elemen induk terlalu rapat atau styling `display: inline-block` yang salah pada `<ruby>`. | Berikan styling CSS: `ruby { line-height: 1; }` dan pastikan induk paragraf memiliki `line-height >= 1.8em`. |
| Input kombinasi keyboard diekspos sebagai satu kesatuan tak terbaca bagi assistive tech. | Penulisan shortcut yang diratakan: `<kbd>Ctrl + C</kbd>`. | Gunakan nesting semantik: `<kbd><kbd>Ctrl</kbd> + <kbd>C</kbd></kbd>`. |
| Browser terminal / text-based browser mencetak karakter ruby tanpa spasi pemisah. | Pengabaian tag fallback `<rp>` (Ruby Fallback Parenthesis). | Selalu sertakan fallback: `<ruby>漢<rp>(</rp><rt>かん</rt><rp>)</rp></ruby>`. |

---

## 11. Best Practices (Production Checklist)

### Semantic & Accessibility Validation
- [ ] Seluruh data input pengguna yang tidak diketahui keterarahan bahasanya telah dibungkus menggunakan elemen `<bdi>`.
- [ ] Tidak ada penggunaan atribut visual manual (seperti styling CSS text-align) untuk memanipulasi keterarahan semantik jika maksud aslinya adalah pemaksaan arah baca (gunakan `<bdo dir="...">` jika data mutlak LTR/RTL).
- [ ] Elemen `<time>` wajib menyertakan atribut `datetime` yang sesuai standar ISO 8601 (tanggal absolut, offset zona waktu, atau format durasi).
- [ ] Struktur penulisan shortcut keyboard menggunakan format bersarang: `<kbd><kbd>Mod</kbd> + <kbd>Key</kbd></kbd>`.
- [ ] Elemen `<abbr>` wajib memiliki atribut `title` yang valid pada kemunculan pertama di dalam satu konteks dokumen panjang.

### Typography & Layout Engineering
- [ ] Elemen `<code>`, `<kbd>`, `<samp>`, dan `<var>` menggunakan stack font monospace sistem atau font berbasis web dengan `font-variant-numeric: tabular-nums` untuk perataan angka pada tabel finansial.
- [ ] Hash string panjang, GUID, atau alamat blockchain diinjeksi dengan `<wbr>` pada titik pemisah struktural agar responsif tanpa merusak seleksi copy-paste.
- [ ] Implementasi `<ruby>` selalu menyertakan pasangan tag `<rp>(</rp>` dan `<rp>)</rp>` untuk mendukung kompatibilitas pembaca dokumen legacy atau non-GUI.

---

## 12. Hands-on Practice

Target Direktori: `hands-on/m02/`

### File: `hands-on/m02/index.html`
Buat berkas dengan konten berikut untuk mengeksekusi pengujian visualisasi isolasi bidirectional, metadata waktu, dan tipografi sistem:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Laboratorium Tipografi Teknis & Lokalisasi HTML</title>
  <style>
    body {
      font-family: sans-serif;
      padding: 2rem;
      background: #f4f4f9;
      color: #333;
    }
    .sandbox-panel {
      background: #fff;
      padding: 1.5rem;
      margin-bottom: 2rem;
      border-radius: 6px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .broken { background-color: #fee2e2; }
    .fixed { background-color: #dcfce7; }
    code { font-family: monospace; color: #b91c1c; }
    kbd { 
      border: 1px solid #aaa; 
      border-radius: 3px; 
      padding: 2px 5px; 
      background: #efefef; 
      font-family: monospace; 
    }
  </style>
</head>
<body>

  <h1>Uji Validasi Arsitektur Semantik Teks</h1>

  <!-- Bagian 1: Pengujian BiDi Bleed -->
  <section class="sandbox-panel">
    <h2>1. Bidirectional Isolation (UBA Testing)</h2>
    
    <div class="broken">
      <p><strong>Rusak (Tanpa &lt;bdi&gt;):</strong></p>
      <!-- Karakter netral tanda seru dan angka akan bergeser -->
      <p>Pengguna: سارة! - Status: Selesai (Skor: 95%).</p>
    </div>

    <div class="fixed">
      <p><strong>Diperbaiki (Dengan &lt;bdi&gt;):</strong></p>
      <!-- Isolasi menjamin tanda seru tetap di dalam skrip Arab -->
      <p>Pengguna: <bdi>سارة!</bdi> - Status: Selesai (Skor: <data value="95">95%</data>).</p>
    </div>
  </section>

  <!-- Bagian 2: Tipografi Instruksional & CLI -->
  <section class="sandbox-panel">
    <h2>2. Technical Typography (Terminal & Shortcuts)</h2>
    <p>
      Untuk merestart daemon microservice, ganti <var>service_name</var> pada baris perintah berikut:
    </p>
    <p>
      <code>sudo systemctl restart <var>service_name</var>.service</code>
    </p>
    <p>
      Jika sistem hang, tekan kombinasi <kbd><kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>F1</kbd></kbd> 
      untuk beralih ke TTY1, lalu periksa respon:
    </p>
    <p>
      <samp>[systemd]: Service failed to bind port 8080: Address already in use.</samp>
    </p>
  </section>

  <!-- Bagian 3: Anotasi Skrip Asia Timur -->
  <section class="sandbox-panel">
    <h2>3. East Asian Phonetic Layout (Ruby)</h2>
    <p>
      Verifikasi kontrak legal mitra Tokyo:
      <ruby>
        株<rp>(</rp><rt>かぶ</rt><rp>)</rp>
        式<rp>(</rp><rt>しき</rt><rp>)</rp>
        会<rp>(</rp><rt>かい</rt><rp>)</rp>
        社<rp>(</rp><rt>しゃ</rt><rp>)</rp>
      </ruby>
      (Kabushiki Gaisha - Korporasi Terbuka).
    </p>
  </section>

</body>
</html>
```

### Prosedur Pengujian:
1. Buka berkas `index.html` menggunakan browser modern (Chrome, Safari, atau Firefox).
2. Periksa Bagian 1: Amati perbedaan posisi tanda seru (`!`) antara baris merah (*broken*) dan baris hijau (*fixed*). Perhatikan bagaimana ketiadaan tag `<bdi>` menyebabkan tanda seru tergeser secara visual karena terpengaruh karakter LTR di sekelilingnya.
3. Buka Accessibility Inspector pada DevTools (Chrome DevTools -> Accessibility Panel). Inspect elemen `<ruby>` dan periksa bagaimana tree memetakan karakter dasar vs anotasi fonetik.

---

## 13. Exercises

### Level Easy
Tuliskan markup HTML semantik yang valid untuk kutipan obrolan pengguna berikut:
> "Untuk menyimpan file, tekan tombol Ctrl dan S bersamaan. Operasi ini memicu eksekusi fungsi `saveDocument(userId)`."

Instruksi: Gunakan kombinasi tag inline `<kbd>`, `<code>`, dan `<var>` yang presisi secara struktural.

### Level Medium
Diberikan sebuah log sistem finansial mentah:
`"User 'محمد_88' transferred 50000 JPY to merchant '佐藤' on 2023-12-01 10:00:00 (Duration: 30 seconds)."`

Instruksi:
Susun struktur HTML enterprise-grade yang memuat elemen:
- `<bdi>` untuk nama pengguna dengan skrip Arab.
- `<data>` untuk nilai transfer mata uang.
- `<ruby>` lengkap dengan `<rp>` dan `<rt>` (bacaan: さとう / Satou) untuk nama merchant Jepang.
- Elemen `<time>` ganda: satu untuk penunjuk waktu absolut ISO 8601 dan satu untuk durasi transaksi 30 detik.

### Level Hard
Buat potongan komponen HTML yang merepresentasikan **Git Diff Semantic Line Viewer**. Komponen harus menyajikan perbandingan satu baris perintah Git:
- Teks lama yang dihapus: `git checkout -b hotfix/payment`
- Teks baru yang dimasukkan: `git switch -c hotfix/payment-v2`
- Menampilkan ID commit SHA-1 yang sangat panjang (40 karakter heksadesimal) menggunakan `<wbr>` setiap 8 karakter agar aman pada resolusi viewport mobile.
- Tetapkan atribut audit semantik lengkap (`<del>`, `<ins>`, `<code>`, `<time>`) beserta atribut `cite` yang mengarah ke URL commit metadata internal.

---

## 14. Challenge

### Studi Kasus: Re-Engineering Realtime Multilingual Chat & FinTech Telemetry Console
Anda ditugaskan merancang *rendering pipeline* berbasis web untuk platform perbankan internasional yang mendukung 12 bahasa (termasuk skrip non-Latin dan RTL: Arab, Urdu, Ibrani, Jepang, Thai).

**Kebutuhan Sistem:**
1. Antarmuka harus menyajikan pesan transaksi yang dikirim secara streaming melalui WebSocket.
2. Setiap entri pesan berisi:
   - Nama pengguna (bisa berbahasa apa saja, termasuk karakter kontrol teks tersembunyi).
   - Kode voucher promo (kombinasi alfanumerik acak LTR, misal: `DISC-99-ARABIC_NAME-2024`).
   - Nominal uang dengan microdata terstruktur.
   - Waktu transaksi relatif yang harus tetap dapat dibaca oleh screen reader sebagai timestamp absolut mikrodetik.
   - Instruksi manual kasir yang memuat kombinasi tombol POS keyboard.
3. **Kendala Produksi (Constraints):**
   - Dilarang keras menggunakan CSS `direction: rtl` atau `direction: ltr` pada level inline tag untuk menyelesaikan masalah keterarahan teks, karena styling ini rentan ter-override oleh utility-first CSS framework (seperti Tailwind CSS) atau user custom styles.
   - Harus memiliki fallback rendering 100% fungsional untuk Lynx/w3m (text-based browser yang sering digunakan auditor server backend).
   - Teks string hash blockchain tidak boleh meluap (*overflow*) dari kontainer kartu pesan, namun ketika disalin (*copy-paste*) oleh pengguna, teks tersebut tidak boleh menyisipkan spasi palsu atau karakter invisible.

**Tugas Anda:**
Tuliskan struktur markup dokumen HTML enterprise definitif beserta catatan arsitektural pemilihan elemen semantik teks level rendah yang menjamin pemenuhan seluruh kriteria di atas tanpa menimbulkan *layout thrashing* dan *BiDi bleeding*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama elemen `<bdi>` dibandingkan elemen `<span>` dengan styling CSS?
   - A. Memberikan efek visual huruf tebal otomatis.
   - B. Mengisolasi arah baca teks dari konteks sekitarnya berdasarkan algoritma UBA.
   - C. Memaksa arah baca teks dari kanan ke kiri secara absolut.
   - D. Menghubungkan teks ke kamus fonetik browser.

2. Elemen HTML manakah yang paling tepat secara semantik untuk menandai output langsung dari sebuah script eksekusi server?
   - A. `<code>`
   - B. `<kbd>`
   - C. `<samp>`
   - D. `<var>`

3. Format string ISO 8601 manakah yang valid untuk atribut `datetime` pada elemen `<time>` yang merepresentasikan durasi 2 jam 30 menit?
   - A. `datetime="2h 30m"`
   - B. `datetime="02:30:00"`
   - C. `datetime="PT2H30M"`
   - D. `datetime="DURATION-2-30"`

4. Apa peran spesifik dari elemen `<rp>` pada implementasi tipografi Ruby?
   - A. Menyediakan styling warna khusus bagi pembaca layar.
   - B. Menyediakan karakter kurung pembatas fallback bagi browser yang tidak mendukung CSS Ruby Layout.
   - C. Menjadi wadah teks utama yang akan dianotasi.
   - D. Mengubah rendering ruby dari atas (*over*) menjadi di bawah (*under*).

5. Manakah elemen yang tepat digunakan untuk menunjukkan variabel dalam persamaan matematika atau parameter kode program?
   - A. `<code>`
   - B. `<kbd>`
   - C. `<var>`
   - D. `<abbr>`

---

### Bagian 2: Intermediate (Analisis Pilihan Ganda & Konseptual)
6. Manakah dari penulisan kombinasi shortcut berikut yang memenuhi standar semantik dan aksesibilitas industri terbaik?
   - A. `<kbd>Ctrl + Shift + R</kbd>`
   - B. `<kbd><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>R</kbd></kbd>`
   - C. `<code><kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>R</kbd></code>`
   - D. `<kbd key="Ctrl+Shift+R">Ctrl + Shift + R</kbd>`

7. Mengapa penggunaan `<wbr>` lebih direkomendasikan untuk string token yang sangat panjang dibandingkan penggunaan properti CSS `word-break: break-all` pada elemen semantik?
   - A. `<wbr>` secara otomatis menambahkan karakter tanda hubung visual (*hyphen*) saat pemotongan baris terjadi.
   - B. CSS `word-break: break-all` merusak kemampuan pembacaan visual kata normal, sedangkan `<wbr>` memberikan kontrol deterministik di titik mana browser boleh memotong baris tanpa merusak integritas kata lain.
   - C. `<wbr>` tidak didukung oleh browser modern, sehingga browser memprioritaskan text wrap standar.
   - D. `<wbr>` mengubah elemen inline menjadi block formatting context.

8. Perhatikan potongan kode berikut:
   ```html
   <p>Invoice status: <bdo dir="rtl">INV-2023-009</bdo></p>
   ```
   Bagaimana karakter tersebut akan dirender secara visual pada layar?
   - A. `INV-2023-009`
   - B. `900-3202-VNI`
   - C. `INV-009-2023`
   - D. Error rendering / blank.

9. Apa perbedaan semantik mendasar antara elemen `<del>` dan `<s>`?
   - A. Tidak ada perbedaan; keduanya adalah alias di HTML5.
   - B. `<s>` menandai teks yang sudah tidak relevan/akurat namun tidak dihapus dari dokumen, sedangkan `<del>` merepresentasikan penghapusan resmi dalam riwayat revisi dokumen.
   - C. `<del>` hanya boleh digunakan di dalam tabel, sedangkan `<s>` di dalam paragraf.
   - D. `<del>` dibaca oleh screen reader, sedangkan `<s>` disembunyikan sepenuhnya dari Accessibility Tree.

10. Kapan Anda harus menggunakan `<data value="...">` daripada `<time datetime="...">`?
    - A. Ketika data yang disajikan berhubungan dengan rentang milidetik.
    - B. Ketika data yang ingin diikatkan ke mesin bukan berupa ekspresi temporal/waktu (misal: ID inventaris, SKU produk, atau nilai mata uang mentah).
    - C. Ketika dokumen tidak menggunakan skrip JavaScript.
    - D. `<data>` digunakan untuk database, `<time>` untuk API browser.

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1**: Pada dashboard perbankan di Mesir (RTL document: `<html dir="rtl">`), nomor referensi tagihan internasional pengguna dicetak sebagai `EG-8821-X`. Namun, pada layar visual, nomor tersebut terpecah dan muncul sebagai `-X8821-EG`. Mengapa hal ini terjadi, dan bagaimana solusinya secara murni menggunakan semantik HTML?
12. **Skenario Kasus 2**: Tim SEO mendeteksi bahwa mesin pencari gagal mengekstrak tanggal artikel yang diperbarui pada platform berita Anda. Markup yang ada saat ini adalah: `<span class="date">Dipublikasikan 2 jam yang lalu</span>`. Mengapa pendekatan ini gagal pada level mesin, dan bagaimana arsitektur markup yang benar?
13. **Skenario Kasus 3**: Pada aplikasi e-learning bahasa Mandarin untuk penutur asing, transkripsi Pinyin ditampilkan di atas karakter Hanzi. Namun, pengguna yang mengakses website via peramban terminal (*text-mode browser*) seperti Lynx pada server Linux melihat karakter Hanzi dan Pinyin melebur menjadi satu kata tanpa jeda yang membingungkan. Elemen semantik apa yang terlewatkan dalam arsitektur markup tersebut?

---

### Kunci Jawaban & Evaluasi

#### Kunci Bagian 1
1. **B**: `<bdi>` bertindak secara khusus untuk menetapkan boundary directional isolate pada algoritma Unicode Bidirectional tanpa memaksakan arah tertentu.
2. **C**: `<samp>` merepresentasikan *sample output* dari program, skrip, atau sistem komputasi.
3. **C**: ISO 8601 Duration untuk format waktu dimulai dengan format penanda periode waktu `PT` (Period of Time), sehingga 2 jam 30 menit ditulis `PT2H30M`.
4. **B**: Elemen `<rp>` (*Ruby Fallback Parenthesis*) menyediakan visualisasi tanda kurung fallback bagi browser yang tidak memiliki modul layout rendering ruby.
5. **C**: Elemen `<var>` secara spesifik diperuntukkan bagi variabel matematika, parameter pemrograman, atau konstanta referensi.

#### Kunci Bagian 2
6. **B**: Pola bersarang `<kbd><kbd>Ctrl</kbd> + <kbd>C</kbd></kbd>` menandakan secara akurat bahwa ada penekanan fisik terpisah pada masing-masing tuts keyboard di dalam satu kesatuan instruksi gesture input.
7. **B**: `<wbr>` memberikan instruksi titik pemecahan baris adaptif yang presisi pada string panjang tanpa memecah kata-kata alami lain secara acak seperti yang terjadi pada `word-break: break-all`.
8. **B**: Tag `<bdo dir="rtl">` melakukan *override* total terhadap urutan karakter; urutan indeks byte dibalik secara visual sehingga glif awal dicetak dari ujung kanan ke kiri (`900-3202-VNI`).
9. **B**: Elemen `<s>` merepresentasikan informasi yang tidak lagi akurat (*strikethrough non-removal*), sedangkan `<del>` adalah entri riwayat penghapusan yang memetakan ke role accessibility `deletion`.
10. **B**: Elemen `<data>` mengasosiasikan konten visual dengan representasi nilai mesin (*machine-readable value*) untuk domain non-temporal.

#### Evaluasi Bagian 3 (Skenario Kasus Produksi)
11. **Analisis Skenario 1**:
    - **Penyebab**: Dokumen induk berada dalam konteks RTL (`dir="rtl"`). String `EG-8821-X` mengandung tanda hubung (`-`) yang merupakan karakter bertipe *Weak/Neutral directional* dalam UBA. Karakter ini ditarik oleh aliran skrip RTL di sekitarnya sehingga posisinya terbalik secara visual.
    - **Solusi**: Bungkus string nomor referensi dengan elemen directional override: `<bdo dir="ltr">EG-8821-X</bdo>` atau isolasi terarah menggunakan `<span dir="ltr">`/`<bdi dir="ltr">EG-8821-X</bdi>`.
12. **Analisis Skenario 2**:
    - **Penyebab**: Elemen `<span>` tidak memiliki semantik mesin; teks visual relatif "2 jam yang lalu" membutuhkan pemrosesan bahasa alami (NLP) yang kompleks dan berubah setiap detik, sehingga crawler mengabaikannya untuk indexing temporal terstruktur.
    - **Solusi**: Transformasikan markup menggunakan elemen `<time>` dengan standardisasi UTC/offset ISO 8601:
      `<time datetime="2023-11-20T14:00:00Z">Dipublikasikan 2 jam yang lalu</time>`.
13. **Analisis Skenario 3**:
    - **Penyebab**: Pengembang hanya mengimplementasikan tag `<ruby>` dan `<rt>` tanpa menyertakan elemen `<rp>` (*Ruby Parenthesis*). Pada browser grafis modern, elemen `<rp>` disembunyikan otomatis, namun pada text-based browser seperti Lynx, ketiadaan `<rp>` menyebabkan karakter teks dasar dan teks fonetik menyatu secara sekuensial tanpa pemisah tanda kurung.
    - **Solusi**: Selalu sertakan tag `<rp>` di sekitar `<rt>`:
      `<ruby>漢<rp>(</rp><rt>hàn</rt><rp>)</rp>字<rp>(</rp><rt>zì</rt><rp>)</rp></ruby>`.

---

## 16. Summary

1. **Integritas Text-Level Semantics**: Elemen seperti `<code>`, `<kbd>`, `<samp>`, `<var>`, `<time>`, dan `<data>` adalah deklarasi kontrak data mesin pada dokumen HTML yang langsung memengaruhi parsing layout engine dan pemetaan objek pada Accessibility Tree (AXTree).
2. **Defensive Bidirectionality (I18N)**: Dalam arsitektur sistem global multi-bahasa, isolasi bidirectional menggunakan `<bdi>` adalah standar mutlak untuk mengkarantina data masukan pengguna yang tidak terpercaya (*untrusted user data*) agar tidak memicu *BiDi bleed* yang merusak perataan antarmuka.
3. **Tipografi Teknis Terstruktur**: Penyusunan dokumentasi teknis modern menuntut pemisahan semantik antara instruksi fisik pengguna (`<kbd>`), ekspresi matematika/variabel (`<var>`), potongan kode (`<code>`), dan keluaran telemetri sistem (`<samp>`).
4. **Resiliensi Tipografi Global**: Dukungan skrip Asia Timur (*East Asian typography*) wajib memanfaatkan CSS Ruby Module melalui struktur semantik `<ruby>`, `<rt>`, dan `<rp>` untuk menjamin degradasi tampilan yang anggun (*graceful degradation*) di seluruh platform komputasi.