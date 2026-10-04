# Bab 03 Module 01: Text-Level Semantics, Tipografi Teknis, dan Lokalisasi

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** `03-Frontend-and-Mobile`
* **Spesialisasi:** Web Architecture, Hypertext Engineering & Accessibility Standards
* **Slug Modul:** `./03-text-level-semantics-tipografi-teknis-dan-lokalisasi/`
* **Level Kompleksitas:** Intermediate to Advanced (Staff Engineer Track)
* **Prasyarat Pengetahuan:**
  * Pemahaman Document Object Model (DOM) Tree Construction
  * Penguasaan HTML5 Block vs Inline-level Flow Architecture
  * Prinsip Dasar Web Accessibility (WCAG 2.2 Level AA/AAA)
  * CSS Box Model, Text Layout Mechanics, dan Bidi Layout Basics
* **Estimasi Waktu Belajar:** 4–6 Jam (Teori Mendalam, Bedah Engine, dan Implementasi Produksi)

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Mendekonstruksi Parsing Semantik Teks HTML5:** Menganalisis bagaimana browser HTML parser dan Accessibility Tree (AOM) memetakan token semantik teks (`<strong>`, `<em>`, `<mark>`, `<time>`, `<data>`, `<ruby>`, `<bdi>`, `<bdo>`) ke dalam Accessible Roles, States, dan Properties.
2. **Menerapkan Tipografi Teknis Presisi Tinggi:** Menguasai representasi semantik kutipan terdistribusi, entitas matematika, kode sumber kompilasi, serta penulisan data tabular/temporal menggunakan elemen teks standar W3C.
3. **Menguasai Internationalization (i18n) dan Directionality Runtime:** Mengimplementasikan bidirectional rendering (LTR/RTL) kompleks berbasis Unicode Bidirectional Algorithm (UBA) melalui isolasi native `<bdi>` dan determinasi eksplisit `<bdo>`, serta anotasi fonetik bahasa Asia Timur melalui `<ruby>`, `<rt>`, dan `<rp>`.
4. **Mencegah Anti-Pola Parsing dan Aksesibilitas:** Mengeliminasi penggunaan tag presentasional (`<b>`, `<i>`, `<font>`) sebagai proxy semantik, serta memastikan Screen Readers (JAWS, NVDA, VoiceOver) membaca teks multibahasa dengan fonetik yang tepat via atribut `lang`.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Text-Level Semantics Bukan Styling Layer
Developer pemula mengasumsikan teks HTML sebagai kanvas visual—memilih tag berdasarkan apakah teks harus miring (*italic*), tebal (*bold*), atau bergaris bawah (*underline*). Ini adalah kesalahan fundamental. 

```
[ Mental Model Salah: Visual Driven ]
Konten Teks ---> "Ingin tebal?" ---> Pakai <b>
            ---> "Ingin miring?" ---> Pakai <i>

[ Mental Model Staff Engineer: Semantic & Machine-Readable ]
Konten Teks ---> "Apakah ada kepentingan mendesak (Urgency/Danger)?" ---> Pakai <strong>
            ---> "Apakah ada penekanan linguistik (Stress Emphasis)?" ---> Pakai <em>
            ---> "Apakah kutipan terminologi/judul karya?" ---> Pakai <cite>
            ---> "Apakah token ini dievaluasi oleh parser lain?" ---> Pakai <time>/<data>
            CSS Engine ---> Bertanggung jawab 100% atas presentasi visual font-weight/style
```

Teks adalah data terstruktur untuk mesin: browser crawler, translasi otomatis, *assistive technologies* (AT), dan pipeline indexing. Tag semantik teks (`text-level semantics`) bertindak sebagai *metadata tokenizers* mikro di dalam aliran teks inline. 

### Prinsip Bidirectional Isolation
Ketika aplikasi web menerima input teks dinamis dari pengguna (User-Generated Content / UGC) dari berbagai belahan dunia, Anda tidak boleh berasumsi aliran teks bersifat unidirectional. Teks bahasa Arab/Hebrew (RTL) yang disuntikkan ke dalam layout LTR dapat merusak urutan render komputasional teks sekitarnya jika tidak diisolasi secara formal. `<bdi>` (Bidirectional Isolation) mengaktifkan sandbox directional pada Unicode Bidirectional Algorithm (UBA), mencegah "leakage" arah tulisan ke token teks tetangga.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Diagram di bawah mengilustrasikan siklus hidup parsing string HTML teks mentah menjadi representasi dualitas: Visual Rendering Pipeline (Layout Tree) dan Accessibility API Pipeline (Accessible Tree), dengan fokus pada determinasi semantik dan directional containment.

```
+-------------------------------------------------------------------------------+
|                       RAW HTML INPUT STREAM (CHARACTERS)                      |
|  "Konfirmasi: <time datetime='2025-05-01'>Mei</time> <bdi>مرحبا</bdi>!"      |
+-------------------------------------------------------------------------------+
                                       |
                                       v
             +---------------------------------------------------+
             |               HTML5 TOKENIZER ENGINE              |
             |       (State Machine: Character Reference State)  |
             +---------------------------------------------------+
                                       |
                                       v
             +---------------------------------------------------+
             |               DOM TREE CONSTRUCTION               |
             |     HTMLSpanElement / HTMLTimeElement / etc.      |
             +---------------------------------------------------+
                                       |
                    +------------------+------------------+
                    |                                     |
                    v                                     v
+---------------------------------------+ +-------------------------------------+
|        STYLE & LAYOUT PIPELINE        | |       ACCESSIBILITY TREE (AOM)      |
|  - Font Matching Algorithm            | |  - Native Semantic Node Assignment  |
|  - CSS Box Generation (Inline Boxes)  | |  - Role: Generic / Time / Text      |
|  - BiDi Level Resolution (Unicode UBA)| |  - Accessible Name Calculation      |
|    * Run Direction Assignment         | |  - Culture/Locale Phonetics Binding |
|    * Neutral Direction Isolation      | |                                     |
+---------------------------------------+ +-------------------------------------+
                    |                                     |
                    v                                     v
+---------------------------------------+ +-------------------------------------+
|             RENDER ENGINE             | |     ASSISTIVE TECHNOLOGY ENGINE     |
|   (Blink/Gecko/WebKit Text Shaper)    | |  - NVDA / VoiceOver / JAWS          |
|  - Glyphs Layout via HarfBuzz         | |  - Screen Reader Braille Display    |
|  - Line Breaking & Inline Layout      | |  - Speech Synthesizer Output:       |
|  - GPU Paint via Skia/CoreGraphics    | |    Pronounces according to `lang`   |
+---------------------------------------+ +-------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Perbedaan Mekanistik: `<strong>` vs `<b>`, `<em>` vs `<i>`

*   `<strong>` (Strong Importance): Mengindikasikan bahwa isinya memiliki tingkat kepentingan, keseriusan, atau urgensi yang tinggi relatif terhadap teks sekitar. Di Accessibility Tree, beberapa pembaca layar mengubah infleksi pitch atau mengumumkan status "important/bold".
*   `<b>` (Bring Attention To): Secara spesifik didefinisikan dalam HTML5 untuk menarik perhatian pada teks tanpa memberikan nilai kepentingan tambahan (misal: kata kunci dalam ringkasan dokumen, nama produk dalam review). AOM menganggap elemen ini bertindak sebagai inline styling token tanpa meningkatkan level semantik kepentingan.
*   `<em>` (Stress Emphasis): Mengubah makna linguistik kalimat secara fundamental berdasarkan penempatan kata. 
*   `<i>` (Idiomatic Text / Alternate Voice): Menandai rentang teks yang diucapkan dengan suara berbeda atau suasana hati lain, seperti istilah teknis, transliterasi, pemikiran batin, atau klasifikasi taksonomi biologi (*Homo sapiens*).

### 2. Time Engine: Anatomi `<time>`
Elemen `<time datetime="...">` memiliki parser internal khusus yang terikat pada spesifikasi parsing algoritma tanggal dan waktu ISO 8601 / RFC 3339.

```
       Visual Rendering Node (Human-Readable)
                 |
                 v
  <time datetime="2025-10-31T20:00:00Z">Malam Ini</time>
        ^
        |
  Machine-Readable Canonical Timestamp (ISO-8601 String)
```

Atribut `datetime` memproses struktur valid:
*   Year: `YYYY` (misal: `2025`)
*   Date: `YYYY-MM-DD` (misal: `2025-10-31`)
*   Time: `HH:MM` atau `HH:MM:SS.FFF` (misal: `20:00:00.000`)
*   Global Date & Time: `YYYY-MM-DDTHH:MM:SSZ` (atau dengan offset zone `+07:00`)
*   Duration: Format ISO `PnYnMnDTnHnMnS` (misal: `PT2H30M` untuk 2 jam 30 menit).

### 3. Bidirectional Isolation Mechanics (`<bdi>` vs `<bdo>`)
Unicode Bidirectional Algorithm (UAX #9) menghitung arah teks berdasarkan jenis karakter:
*   **Strong Characters:** Karakter alfabet Latin (LTR) atau alfabet Arab/Hebrew (RTL). Karakter ini memaksa arah teks.
*   **Neutral Characters:** Tanda baca, spasi, simbol (`!`, `@`, `/`, `.`, `1-9`). Arahnya ditentukan oleh karakter "Strong" di sekelilingnya.

Jika nama pengguna Arab (`مرحبا`) diikuti tanda seru (`!`) di dalam antarmuka LTR:
*   Tanpa isolasi: Browser melihat `مرحبا!` dan karena tanda seru adalah neutral, ia diserap ke dalam alur RTL `مرحبا`, menyebabkan letak tanda seru melompat secara keliru ke sisi kiri string.
*   Menggunakan `<bdi>`: Elemen ini mengimplementasikan instruksi `unicode-bidi: isolate` pada level engine, mengunci konteks karakter netral di dalam sandbox directional internal tanpa bocor keluar.
*   Menggunakan `<bdo>`: Memaksa override mutlak (`unicode-bidi: bidi-override`) mengabaikan algoritma bidirectional native, membalik arah render karakter secara paksa.

### 4. Fonetik Asia Timur: Anatomi `<ruby>`
```
         +-----------------------+  <-- Anotasi Fonetik (Furigana / Pinyin)
         |      かん     じ      |      Elemen: <rt>
         +-----------------------+
         |      漢       字      |  <-- Teks Dasar (Kanji / Hanzi)
         +-----------------------+      Elemen: Base Text
```
Elemen `<rp>` (Ruby Fallback Parenthesis) adalah mekanisme backward compatibility. Parser modern menyembunyikan tag `<rp>`, sementara mesin kuno (non-ruby-aware) akan merendernya sebagai tanda kurung biasa: `漢字(かんじ)`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Unicode Bidirectional Algorithm (UBA) & CSS Counterparts
Dalam CSS Writing Modes Level 3, elemen semantik teks memiliki padanan CSS `unicode-bidi` baku:

| Elemen HTML | User-Agent Default CSS Property | Penjelasan Operasional |
| :--- | :--- | :--- |
| `<bdi>` | `unicode-bidi: isolate;` | Menghitung Bidi level di dalam node secara independen dari container luar. |
| `<bdo dir="rtl">` | `unicode-bidi: bidi-override; direction: rtl;` | Memaksa pemrosesan arah run karakter terlepas dari sifat Strong/Weak Unicode char. |
| `<q>` | `display: inline; quotes: auto;` | Menyuntikkan tanda kutip otomatis sesuai lokalisasi dokumen via pseudo-elemen `::before`/`::after`. |

### Tipografi Semantik: Subskrip, Superskrip, dan Perubahan Dokumen
*   `<sub>` dan `<sup>`: Tidak boleh digunakan semata-mata untuk styling eksponen atau posisi vertikal (misal: memindahkan ikon). Gunakan `<sup>` secara semantik untuk referensi catatan kaki (*footnote*), indeks matematika, atau nomor ordinal bahasa Prancis (1<sup>er</sup>). Gunakan `<sub>` untuk rumus kimia ($H_2O$) atau variabel matematika berindeks ($x_1$).
*   `<ins>` dan `<del>`: Merupakan satu-satunya elemen tipografi teks yang mendukung pelacakan perubahan temporal formal melalui atribut `cite` (URI ke alasan perubahan) dan `datetime` (waktu modifikasi dilakukan).
*   `<mark>`: Merepresentasikan teks yang disorot untuk tujuan referensi sekunder atau konteks pencarian saat ini, yang relevan bagi pembaca pada saat itu, bukan oleh penulis asli dokumen.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi komprehensif implementasi elemen semantik teks, penanganan bidirectional, dan anotasi tipografi presisi.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fundamental Text-Level Semantics Showcase</title>
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 2rem auto;
      padding: 0 1rem;
    }
    pre {
      background: #f4f4f5;
      padding: 1rem;
      border-radius: 4px;
      overflow-x: auto;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      background: #e4e4e7;
      padding: 0.2em 0.4em;
      border-radius: 3px;
      font-size: 0.875em;
    }
    pre code {
      background: transparent;
      padding: 0;
    }
    del {
      background-color: #fee2e2;
      color: #991b1b;
    }
    ins {
      background-color: #dcfce7;
      color: #166534;
      text-decoration: none;
      border-bottom: 2px solid #166534;
    }
  </style>
</head>
<body>

  <!-- Bagian 1: Strong, Em, Mark, Small -->
  <section>
    <h2>1. Penekanan dan Urgensi</h2>
    <p>
      <strong>Peringatan Keamanan:</strong> Jangan pernah membagikan kata sandi Anda. 
      Tindakan ini <em>sangat</em> dilarang dalam SOP infrastruktur kami.
    </p>
    <p>
      Hasil penelusuran kata kunci: Menampilkan data untuk <mark>infrastruktur</mark> jaringan.
    </p>
    <p>
      <small>Hak Cipta &copy; 2025 Platform Enterprise. Seluruh hak cipta dilindungi undang-undang.</small>
    </p>
  </section>

  <!-- Bagian 2: Sub, Sup, Wbr, Code, Kbd, Samp -->
  <section>
    <h2>2. Tipografi Teknis dan Komputasi</h2>
    <p>
      Persamaan Kimia: Reaksi glukosa menghasilkan 2 C<sub>2</sub>H<sub>5</sub>OH + 2 CO<sub>2</sub>.
      Teorema Terakhir Fermat: a<sup>n</sup> + b<sup>n</sup> &ne; c<sup>n</sup> untuk n &gt; 2.
    </p>
    <p>
      Untuk menyalin log direktori panjang:
      <code>/var/log/audit/system-daemon-application-monitoring-<wbr>production-instance-eu-west-1.log</code>
    </p>
    <p>
      Tekan <kbd><kbd>Ctrl</kbd> + <kbd>C</kbd></kbd> untuk membatalkan proses eksekusi.
      Jika berhasil, terminal akan merespons dengan: <samp>Process terminated with exit code 130</samp>.
    </p>
  </section>

  <!-- Bagian 3: Time, Data, Cite, Q -->
  <section>
    <h2>3. Temporal, Data Machine-Readable, dan Kutipan</h2>
    <p>
      Deploy rilis versi 4.2.0 dijadwalkan pada 
      <time datetime="2025-11-15T14:30:00+07:00">15 November 2025 pukul 14:30 WIB</time>.
      SLA downtime maksimum adalah <time datetime="PT45M">45 menit</time>.
    </p>
    <p>
      Produk teridentifikasi: <data value="SKU-889120-X">Enterprise Gateway Core v2</data>.
    </p>
    <p>
      Berdasarkan publikasi monumental <cite>The Art of Computer Programming</cite>,
      Donald Knuth menyatakan bahwa <q cite="https://www-cs-faculty.stanford.edu/~knuth/">Premature optimization is the root of all evil</q>.
    </p>
  </section>

  <!-- Bagian 4: Del, Ins, S -->
  <section>
    <h2>4. Modifikasi Dokumen dan Audit Trail</h2>
    <p>
      Status API v1: <s>Sepenuhnya didukung hingga 2026</s> (Ditinggalkan).
    </p>
    <p>
      Pembaruan Kebijakan Data: Batas retensi log penyimpanan adalah 
      <del datetime="2025-01-01T00:00:00Z" cite="#rfc-092">30 hari</del>
      <ins datetime="2025-01-01T00:00:00Z" cite="#rfc-092">90 hari</ins> sesuai standar compliance ISO/IEC 27001.
    </p>
  </section>

  <!-- Bagian 5: BDI, BDO, Ruby -->
  <section>
    <h2>5. Internasionalisasi (i18n), BiDi, dan Karakter Kompleks</h2>
    <p>
      Peringkat Pengguna Komunitas:
      <!-- Menggunakan BDI untuk mengisolasi username bidi dari layout sistem -->
      User 1: <bdi>Sarah_Dev</bdi> - Skor: 100 poin.<br>
      User 2: <bdi>فاطمة</bdi> - Skor: 95 poin.<br>
      User 3: <bdi>יוסף</bdi> - Skor: 92 poin.
    </p>
    <p>
      Override Directional Paksa (Testing Font):
      <bdo dir="rtl">Teks ini ditulis terbalik secara manual dari kanan ke kiri.</bdo>
    </p>
    <p>
      Anotasi Fonetik Kanji Jepang:
      <ruby>
        東 <rp>(</rp><rt>とう</rt><rp>)</rp>
        京 <rp>(</rp><rt>きょう</rt><rp>)</rp>
      </ruby>
    </p>
  </section>

</body>
</html>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 48:** `<strong>Peringatan Keamanan:</strong>`  
    Parser mengikat node ini ke role strong importance. Screen reader mengomunikasikan tingkat keparahan/urgensi kata pembuka kepada pengguna tunanetra, berbeda dengan styling font murni via CSS `font-weight: 700`.
*   **Baris 49:** `<em>sangat</em>`  
    Menyisipkan *stress emphasis*. Sintesis vokal *Text-to-Speech* (TTS) akan mengubah kurva intonasi akustik dan pitch pada kata "sangat", menandakan kontras vokal.
*   **Baris 52:** `<mark>infrastruktur</mark>`  
    Menunjukkan relevansi kontekstual saat ini (run-time relevance). Browser memetakan warna sorot *default* (`mark { background-color: mark; color: marktext; }`), dan AOM menetapkan semantik *highlighted*.
*   **Baris 55:** `<small>Hak Cipta ...</small>`  
    Bukan instruksi untuk sekadar mengecilkan ukuran teks. Dalam HTML5, `<small>` merepresentasikan *side-comments* dan *fine print*, seperti teks disclaimer hukum, hak cipta, atau lisensi.
*   **Baris 62:** `C<sub>2</sub>H<sub>5</sub>OH` & `a<sup>n</sup>`  
    Karakter `2`, `5`, dan `n` di-render sebagai subskrip dan superskrip secara inline. Elemen ini mempertahankan keterbacaan struktur matematis/kimiawi tanpa mengaburkan parsing string teks dasar.
*   **Baris 67:** `...monitoring-<wbr>production...`  
    Elemen `<wbr>` (Word Break Opportunity) memberi tahu rendering engine bahwa teks yang panjang tanpa spasi ini diizinkan untuk dipecah barisnya tepat pada posisi ini jika kontainer mengalami *overflow*. Jika kontainer cukup lebar, pemecahan baris tidak dilakukan.
*   **Baris 70:** `<kbd><kbd>Ctrl</kbd> + <kbd>C</kbd></kbd>`  
    Nesting elemen `<kbd>` merepresentasikan kombinasi keystroke. Elemen luar mewakili keseluruhan gestur input, sedangkan elemen dalam menandai tuts spesifik.
*   **Baris 71:** `<samp>Process terminated with exit code 130</samp>`  
    Menandakan keluaran sampel (*sample output*) dari program komputer atau skrip, memisahkannya secara semantik dari kode sumber (`<code>`).
*   **Baris 78:** `<time datetime="2025-11-15T14:30:00+07:00">...`  
    Atribut `datetime` membedah representasi visual non-standar menjadi format waktu mesin absolut terstandardisasi dengan offset zona waktu (`+07:00`).
*   **Baris 80:** `<time datetime="PT45M">45 menit</time>`  
    Menggunakan skema durasi ISO 8601 (`P` = Period, `T` = Time component, `45M` = 45 Minutes). Mesin pencari atau asisten pintar mengekstrak ini sebagai metrik rentang waktu.
*   **Baris 83:** `<data value="SKU-889120-X">...`  
    Mengaitkan representasi data tabular/katalog dengan ID/nilai internal backend tanpa harus menampilkan ID mentah tersebut secara visual kepada end-user.
*   **Baris 86–87:** `<cite>` dan `<q cite="...">`  
    `<cite>` menandai judul karya intelektual (*The Art of Computer Programming*). Elemen `<q>` membungkus kutipan inline, menyuntikkan tanda petik typografis lokal, serta menyematkan URL asal kutipan via atribut `cite`.
*   **Baris 94:** `<s>Sepenuhnya didukung...</s>`  
    Menandakan informasi yang tidak lagi akurat atau tidak lagi relevan, tetapi tidak dihapus secara formal dari riwayat dokumen (berbeda dari `<del>`).
*   **Baris 98–99:** `<del datetime="...">` dan `<ins datetime="...">`  
    Menyusun audit log langsung di dalam dokumen. Menunjukkan bahwa nilai "30 hari" dihapus dan digantikan oleh "90 hari" pada stempel waktu tertentu.
*   **Baris 108–110:** `<bdi>فاطمة</bdi>` dan `<bdi>יوسף</bdi>`  
    Menginstruksikan Bidirectional Engine untuk mengisolasi string RTL Arab dan Ibrani. Tanda hubung (`-`) dan angka (`95 poin`) di luarnya tetap mengikuti alur LTR dokumen secara stabil tanpa tertukar posisinya.
*   **Baris 113:** `<bdo dir="rtl">...`  
    Memaksa algoritma BiDi untuk mengabaikan struktur asli dan membalikkan alur visual string teks secara total.
*   **Baris 116–121:** `<ruby>`, `<rt>`, `<rp>`  
    Merender panduan baca fonetik. Tag `<rp>` melindungi klien lama dengan merender tanda kurung di sekitar bacaan `<rt>` jika browser tidak mendukung tipografi Ruby.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Financial Settlement & Multi-Region Audit Log Interface
Sebuah platform perbankan global (SaaS Fintech) beroperasi di pasar global (termasuk Timur Tengah, Jepang, dan Asia Tenggara). Sistem memiliki layar **Transaction Settlement Stream** yang menampilkan data dinamis dari ribuan entitas:
*   Username pelanggan internasional (mengandung karakter Latin, Cyrillic, Kanji, dan Arab).
*   Nominal valuta asing, status transaksi, timestamp transaksi mikro-detik (UTC).
*   Audit jejak perubahan nilai tukar mata uang yang dimodifikasi oleh dealer valas secara manual.
*   Nama instrumen finansial dalam karakter Kanji Jepang beserta pembacaannya.

### Masalah Arsitektural Sebelumnya:
1.  Username Arab (`عمر_فاروق`) merusak alignment visual tanda titik dua, timestamp, dan angka desimal di tabel LTR (Gejala: *BiDi bleeding*). Angka desimal `12.50` terbalik menjadi `50.12`.
2.  Screen Reader tuna netra gagal melafalkan timestamp ISO dan membingungkan operator perbankan tunanetra saat membaca perubahan status kontrak swap.
3.  Audit trail modifikasi status transaksi ditulis menggunakan `<s>` dan `<span>` biasa tanpa stempel waktu ISO mesin, menyebabkan sistem agregasi otomatis gagal mengekstraksi data riwayat perbankan.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah komponen tabel audit transaksi berstandar enterprise yang mengatasi seluruh masalah di atas menggunakan HTML5 Text-Level Semantics dan manipulasi DOM modern:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Global Settlement Audit Stream</title>
  <style>
    :root {
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      --bg-surface: #ffffff;
      --text-main: #09090b;
      --text-muted: #71717a;
      --border-color: #e4e4e7;
      --del-bg: #fee2e2;
      --ins-bg: #dcfce7;
      --highlight: #fef08a;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8fafc;
      color: var(--text-main);
      padding: 2rem;
      margin: 0;
    }

    .table-container {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow-x: auto;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.875rem;
    }

    th, td {
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border-color);
      vertical-align: middle;
    }

    th {
      background: #f1f5f9;
      font-weight: 600;
      color: #334155;
    }

    /* Tipografi Teknis Finansial */
    .numeric-cell {
      font-variant-numeric: tabular-nums lining-nums;
      font-family: var(--font-mono);
    }

    mark.audit-highlight {
      background: var(--highlight);
      padding: 0.1rem 0.3rem;
      border-radius: 2px;
      font-weight: 500;
    }

    del.audit-delta {
      background: var(--del-bg);
      color: #991b1b;
      text-decoration: line-through;
      padding: 0.1rem 0.2rem;
    }

    ins.audit-delta {
      background: var(--ins-bg);
      color: #166534;
      text-decoration: none;
      border-bottom: 1px solid #166534;
      padding: 0.1rem 0.2rem;
    }

    ruby {
      font-size: 0.9em;
    }

    ruby rt {
      font-size: 0.65em;
      color: var(--text-muted);
    }

    .meta-subtext {
      color: var(--text-muted);
      display: block;
      font-size: 0.75rem;
    }
  </style>
</head>
<body>

  <h1>Log Penyelesaian Transaksi Real-Time (Multi-Region)</h1>
  
  <div class="table-container">
    <table>
      <thead>
        <tr>
          <th>ID Referensi</th>
          <th>Stempel Waktu (ISO-8601)</th>
          <th>Counterparty (Inisiator)</th>
          <th>Aset & Instrumen</th>
          <th>Nilai Eksekusi</th>
          <th>Status Rekonsiliasi</th>
        </tr>
      </thead>
      <tbody id="settlement-stream">
        <!-- Record 1: RTL BiDi Username + Modification Tracking -->
        <tr>
          <td class="numeric-cell">
            <code>TX-90123-A</code>
          </td>
          <td>
            <time datetime="2025-05-18T10:14:32.124Z">
              18 Mei 2025, 10:14:32 UTC
            </time>
          </td>
          <td>
            <!-- Proteksi BiDi Leakage untuk nama Arab -->
            <bdi lang="ar" dir="rtl">علي عبد الله</bdi>
            <span class="meta-subtext">ID: <data value="ACC-44910">44910</data></span>
          </td>
          <td>
            USD / SAR
          </td>
          <td class="numeric-cell">
            <del datetime="2025-05-18T10:15:00Z" cite="#auditor-404">3.7505</del>
            <ins datetime="2025-05-18T10:15:00Z" cite="#auditor-404">3.7512</ins>
          </td>
          <td>
            <span class="badge">
              <strong>SETTLED</strong> (Manual Override)
            </span>
          </td>
        </tr>

        <!-- Record 2: Japanese Ruby Typography + Highlight + Ordinal -->
        <tr>
          <td class="numeric-cell">
            <code>TX-90124-B</code>
          </td>
          <td>
            <time datetime="2025-05-18T10:16:05.890Z">
              18 Mei 2025, 10:16:05 UTC
            </time>
          </td>
          <td>
            <bdi lang="ja">高橋 健太</bdi>
            <span class="meta-subtext">ID: <data value="ACC-11029">11029</data></span>
          </td>
          <td>
            <!-- Anotasi Fonetik untuk Aset Obligasi Pemerintah Jepang -->
            <ruby>
              国 <rp>(</rp><rt>こく</rt><rp>)</rp>
              債 <rp>(</rp><rt>さい</rt><rp>)</rp>
            </ruby>
            <span>JGB 10-Yr 2<sup>nd</sup> Gen</span>
          </td>
          <td class="numeric-cell">
            <mark class="audit-highlight">&yen; 10,000,000</mark>
          </td>
          <td>
            <em>Dalam Kliring</em>
          </td>
        </tr>

        <!-- Record 3: Command & Response Sampling -->
        <tr>
          <td class="numeric-cell">
            <code>TX-90125-C</code>
          </td>
          <td>
            <time datetime="2025-05-18T10:18:22.000Z">
              18 Mei 2025, 10:18:22 UTC
            </time>
          </td>
          <td>
            <bdi>Apex_HFT_Bot_01</bdi>
            <span class="meta-subtext">Automated Gateway</span>
          </td>
          <td>EUR / USD</td>
          <td class="numeric-cell">1.0845</td>
          <td>
            <samp>STATUS_OK_200</samp>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <script>
    /**
     * Engine Parsing Telemetri Client-side
     * Membuktikan kemudahan ekstraksi data berbasis elemen semantic standar
     */
    function extractAuditMetrics() {
      const rows = document.querySelectorAll('#settlement-stream tr');
      const metrics = [];

      rows.forEach(row => {
        const timeEl = row.querySelector('time');
        const bdiEl = row.querySelector('bdi');
        const dataEl = row.querySelector('data');
        const delEl = row.querySelector('del');
        const insEl = row.querySelector('ins');

        metrics.push({
          timestamp: timeEl ? timeEl.getAttribute('datetime') : null,
          initiatorName: bdiEl ? bdiEl.textContent : null,
          initiatorLocale: bdiEl ? bdiEl.getAttribute('lang') || 'unknown' : null,
          accountId: dataEl ? dataEl.value : null,
          hasModifications: !!(delEl && insEl),
          deltaDetails: (delEl && insEl) ? {
            from: delEl.textContent,
            to: insEl.textContent,
            reasonRef: insEl.getAttribute('cite'),
            modifiedAt: insEl.getAttribute('datetime')
          } : null
        });
      });

      return metrics;
    }

    // Eksekusi Audit Logging Engine
    console.log('[AUDIT TELEMETRY EXTRACTED]:', extractAuditMetrics());
  </script>
</body>
</html>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Elemen Semantik | Alternatif Non-Semantik | Dimensi Evaluasi | Analisis Trade-off & Damp