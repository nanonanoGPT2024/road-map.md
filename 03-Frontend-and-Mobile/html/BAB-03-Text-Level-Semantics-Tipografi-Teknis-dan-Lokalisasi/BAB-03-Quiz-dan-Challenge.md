# BAB 03: Quiz, Challenge, & Knowledge Check
**Text-Level Semantics, Tipografi Teknis, dan Lokalisasi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Pemetaan Accessibility Tree pada Tipografi Semantik vs Presentasional
Jelaskan perbedaan deterministik antara pasangan elemen `<b>`/`<i>` dan `<strong>`/`<em>` dalam konteks konstruksi Accessibility Tree (AOM) dan engine Speech Synthesis (Text-to-Speech / TTS). Mengapa browser modern tidak lagi menganggap `<b>` dan `<i>` sepenuhnya *obsolete*, melainkan mendefinisikan ulang makna semantik murninya di dalam spesifikasi HTML5?

### Soal 1.2: Peran Fungsional Tag `<time>` dan Atribut `datetime` dalam Machine-Readability
Diberikan representasi waktu manusia: *"Kemarin lusa jam 3 sore"*. Mengapa peramban dan web crawler (search indexing engine) membutuhkan elemen `<time datetime="...">` dengan standar ISO 8601 / RFC 3339? Jelaskan skenario parsing mesin di mana kelalaian menyediakan atribut `datetime` yang valid dapat merusak ekstraksi semantic rich snippets pada search engine.

### Soal 1.3: Keterbatasan Arsitektural Elemen `<abbr>` pada Mobile Touch-Screen
Secara historis, singkatan didefinisikan menggunakan `<abbr title="HyperText Markup Language">HTML</abbr>`. Mengapa pendekatan ini dikategorikan sebagai *anti-pattern* pada perangkat berbasis sentuh (touch-first UI) dan teknologi asistif tingkat lanjut? Bagaimana pola desain HTML semantik modern menyelesaikan dilema *progressive disclosure* untuk definisi akronim tanpa mengandalkan event `hover` bawaan browser?

### Soal 1.4: Arsitektur Parsing dan Mekanisme Fallback Elemen `<ruby>`, `<rt>`, dan `<rp>`
Uraikan pohon DOM (DOM Tree) yang dihasilkan oleh parser HTML ketika merender anotasi fonetik Asia Timur (furigana/pinyin) menggunakan elemen `<ruby>`, `<rt>`, dan `<rp>`. Jelaskan secara presisi apa yang terjadi pada *user-agent* warisan (legacy) atau parser non-GUI (seperti terminal web browser) saat memproses tag `<rp>` (Ruby Parentheses).

### Soal 1.5: Taksonomi Semantik Kode Teknis: `<code>`, `<samp>`, `<kbd>`, dan `<var>`
Dalam dokumentasi antarmuka baris perintah (CLI), terdapat input pengguna, variabel lingkungan, eksekusi program, dan log pesan kesalahan. Petakan masing-masing entitas data teknis tersebut ke elemen `<code>`, `<samp>`, `<kbd>`, dan `<var>`. Jelaskan mengapa mencampuradukkan keempat elemen ini ke dalam tag generik `<code>` menurunkan skor aksesibilitas kognitif dan mempersulit automasi syntax highlighting berbasis AST (Abstract Syntax Tree).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Unicode Bidirectional Algorithm (UBA) Spillover dan Resolusi `<bdi>` vs `<bdo>`
Perhatikan kasus rendering teks berikut di mana nama pengguna Arab disisipkan secara dinamis ke dalam kalimat bahasa Inggris:
```html
<p>User Sarah updated her status: 3 minutes ago.</p>
<!-- Kasus UGC (User Generated Content) dengan bahasa Arab: -->
<p>User سارة updated her status: 3 minutes ago.</p>
```
Sering kali, angka "3" atau tanda titik terlempar ke sisi kiri teks Arab karena *neutral directional characters* diserap oleh konteks skrip RTL di sekitarnya. 
1. Mengapa CSS `direction: rtl` atau tag `<bdo>` bukan solusi yang tepat untuk kasus ini?
2. Bagaimana elemen `<bdi>` (Bi-directional Isolation) secara internal menginstruksikan layout engine peramban untuk menerapkan *first-strong directional isolate* pada Unicode Bidirectional Algorithm (UBA)?

### Soal 2.2: Line-Breaking Mechanics: Evaluasi Komparatif `<wbr>`, `&shy;`, dan CSS `hyphens: auto`
Bandingkan perilaku layout engine (seperti Blink atau WebKit) ketika menghitung *breaking opportunities* untuk kata teknis yang panjang (misalnya: `Supercalifragilisticexpialidocious` atau path direktori Unix `/usr/local/var/log/system.log`) menggunakan:
1. Elemen HTML `<wbr>`
2. Karakter entitas `&shy;` (Soft Hyphen)
3. Properti CSS `hyphens: auto` yang dipadukan dengan atribut `lang`

Jelaskan dampak masing-masing pendekatan terhadap teks yang disalin (*copy-paste buffer*) ke clipboard sistem operasi pengguna.

### Soal 2.3: Mitigasi Layout Shift Finansial melalui Tabular Figures dan Semantik `<data>`
Dalam aplikasi dashboard trading frekuensi tinggi (HFT), nilai mata uang kripto terus diperbarui setiap 100 milidetik:
```html
<div class="ticker">
  <data value="64230.15">$64,230.15</data>
</div>
```
Angka-angka tersebut mengalami getaran horizontal (*layout jitter / horizontal layout shift*) yang merusak stabilitas visual UI karena lebar glyph proportional font berbeda (misalnya karakter "1" lebih sempit daripada "8"). 
1. Jelaskan bagaimana kombinasi semantik tag `<data>` dan fitur OpenType CSS (`font-variant-numeric: tabular-nums`) menyelesaikan masalah rendering ini pada tingkat sub-pixel layout!
2. Mengapa tidak menggunakan `<span class="crypto-val">` biasa dari kacamata web scraper dan arsitektur data?

### Soal 2.4: Hierarki Resolusi Tipografi Kuotasi Lintas Bahasa (`<q>` dan `lang`)
Diberikan struktur markup nested quotes berikut:
```html
<article lang="fr">
  <p>L'orateur a dit: <q>Nous devons respecter les normes du <q lang="en">W3C Consortium</q> avant tout.</q></p>
</article>
```
1. Jelaskan secara mekanis bagaimana browser menentukan glyph tanda kutip (quotes) luar (French guillemets `« »`) dan kutip dalam (English quotation marks `“ ”`) secara otomatis.
2. Apa yang terjadi jika atribut `lang` dihilangkan atau dideklarasikan secara tidak valid (misalnya `lang="xx"`)? Bagaimana algoritma penentuan fallback glyph berjalan di CSS rendering engine?

### Soal 2.5: Aksesibilitas Semantik Mutasi Konten: Kegagalan `<del>` dan `<ins>` pada Screen Reader
Secara visual, browser merender `<del>` dengan *strikethrough* dan `<ins>` dengan *underline*. Namun, mayoritas screen reader (seperti NVDA atau VoiceOver) secara default **tidak** mengumumkan perubahan status pencabutan atau penambahan teks tersebut (keduanya dibaca secara monoton sebagai teks biasa) untuk menghindari kebisingan audio.
1. Bagaimana Anda mengonfigurasi markup dokumen yang memuat `<del>` dan `<ins>` agar perubahan status mutasi (misalnya: riwayat revisi perjanjian hukum atau perubahan harga diskon) tetap dapat dipahami oleh pengguna disabilitas netra secara deterministik tanpa merusak tata letak visual?
2. Evaluasi penggunaan atribut `aria-label`, hidden text (`.sr-only`), atau ARIA live regions dalam konteks ini.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Layout Thrashing & Bidi Performance Degradation pada Global Live-Chat
*Konteks Skala*: Anda adalah Lead Frontend Architect di aplikasi web enterprise streaming global. Terdapat panel live-chat yang menerima 2.500 pesan per detik dari jutaan pengguna simultan di seluruh dunia, mencakup skrip Latin, Arab (RTL), Ibrani (RTL), dan Jepang (CJK).
*Gejala Masalah*: Analisis profiler menunjukkan `Recalculate Style` dan `Layout` memakan waktu hingga 45ms per frame (mengakibatkan *frame drop* ekstrem hingga 15-20 FPS). Investigasi mendalam menemukan bahwa browser berulang kali mengevaluasi arah paragraf dari teks dinamis tanpa arah eksplisit dan mengalami *Bidi re-ordering cost* yang masif. Beberapa developer mencoba memperbaikinya dengan membungkus teks menggunakan `<span style="direction: rtl;">` jika mendeteksi karakter non-Latin via regex sederhana di JavaScript.
*Pertanyaan Diagnostik & Arsitektural*:
1. Mengapa manipulasi CSS `direction` berbasis inferensi JS regex justru memperburuk performa CPU dan memicu bug arah tanda baca (*spillover effect*) pada pesan campuran (*mixed-direction messages*)?
2. Rancang struktur markup HTML murni yang optimal untuk setiap item pesan chat agar peramban dapat mengisolasi kalkulasi BiDi ke tingkat sub-pohon tanpa memicu *layout recalculation cascade* ke seluruh kontainer obrolan!
3. Sebutkan atribut dan nilai HTML5 native yang menyerahkan deteksi arah teks sepenuhnya ke level engine peramban secara *per-message basis* dengan performa paling teroptimasi!

### Skenario B: Kerusakan Data Rekonsiliasi Faktur Pajak Multinasional akibat Kegagalan Lokalisasi Teks
*Konteks Skala*: Sebuah platform ERP logistik lintas-negara memproses jutaan PDF faktur pajak yang di-render secara headless menggunakan Chromium Engine dari template HTML/CSS. 
*Gejala Masalah*: Pada faktur untuk entitas bisnis di Jerman (`de-DE`), Turki (`tr-TR`), dan Uni Emirat Arab (`ar-AE`), terjadi insiden finansial fatal:
- Nilai total `1.500,00` (Jerman: seribu lima ratus euro) terbaca dan diparsing oleh mesin klien/crawler downstream sebagai `1.5` (satu koma lima).
- Operasi string CSS `text-transform: uppercase` pada kata `fatura` dalam konteks Turki menghasilkan karakter `FATURA` bukannya `FATURA` dengan dotted I (`İ`), menyebabkan pembatalan validitas faktur di otoritas pajak Turki.
- Teks nomor referensi kontainer pengiriman internasional `#TR-8921-X` pada faktur berbahasa Arab terbalik menjadi `X-8921-TR#`, menyebabkan kegagalan scan barcode/OCR di pelabuhan.
*Pertanyaan Diagnostik & Solusi*:
1. Bedah secara menyeluruh akar masalah markup HTML dari ketiga malfungsi di atas!
2. Rekonstruksi struktur elemen semantik HTML (termasuk penerapan atribut `lang`, elemen `<data>`, `<bdi>`, dan tata kelola tipografi teknis) untuk memastikan dokumen tersebut aman secara legal, kebal parsing error downstream, dan mempertahankan integritas visual OCR!

### Skenario C: Trade-off Arsitektural Portal Dokumentasi API Multi-Skrip (CJK + BiDi)
*Konteks Skala*: Anda sedang merancang Core Design System untuk platform dokumentasi developer public-facing yang mendukung 24 bahasa secara native, menampilkan kode CLI, endpoint HTTP, diff schema JSON, dan istilah teknis lokal (misal: istilah pemrograman yang memiliki furigana/rubi di Jepang, teks RTL di Timur Tengah).
*Dilema Arsitektur*: Tim internal terpecah menjadi dua kubu:
- *Kubu A*: Mengusulkan abstraksi berbasis komponen generik universal: Semua teks dibungkus `<div>` dan `<span>` dengan styling utilitas class yang sangat padat, menyerahkan seluruh pemformatan tipografi, pemenggalan kata, dan kutipan pada library JavaScript runtime i18n pihak ketiga.
- *Kubu B*: Menuntut arsitektur murni *Strict Text-Level Semantics*: Memaksimalkan penggunaan `<bdi>`, `<ruby>`, `<rt>`, `<rp>`, `<kbd>`, `<samp>`, `<var>`, `<wbr>`, CSS Logical Properties, dan BCP 47 language tagging murni di level HTML tanpa dependensi JS runtime untuk rendering teks.
*Pertanyaan Analisis & Keputusan*:
1. Analisis *trade-off* mendalam antara kedua pendekatan tersebut ditinjau dari metrik: Cumulative Layout Shift (CLS), First Input Delay/INP, TTFB (Payload Size), SEO/Crawler indexing capability, dan *DOM Tree Memory Footprint*.
2. Sebagai Principal Engineer, susun rekomendasi arsitektur final: Di mana batasan tegas tanggung jawab HTML semantik teks vs tanggung jawab JavaScript formatting libraries (seperti `Intl` API)?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi Engine "Terminal-to-HTML Diagnostic Report" Berstandar Aksesibilitas Internasional & Multi-Skrip

#### 1. Problem Statement
Anda ditugaskan membangun generator template HTML statis untuk sistem audit keamanan infrastruktur global. Sistem ini menghasilkan log diagnostik yang menggabungkan:
1. Perintah CLI yang dijalankan oleh operator dengan hak akses root.
2. Respons terminal/mesin (stdout/stderr) yang mencakup parameter dinamis, nilai memori hexadecimal, dan waktu pemrosesan ISO.
3. Catatan revisi audit (teks yang dicabut dan teks pengganti).
4. Komentar audit manusia yang ditulis dalam bahasa campuran: Bahasa Inggris, teks berarah kanan-ke-kiri (RTL - Arab/Ibrani), dan istilah teknis sistem dalam bahasa Jepang yang membutuhkan pelafalan fonetik (Ruby).
5. Nilai metrik sistem kuantitatif (CPU, Latency, Bandwidth) yang tidak boleh menyebabkan layout jitter ketika dipantau secara visual.

Template ini harus dirender tanpa JavaScript tambahan, sepenuhnya mematuhi standar HTML5 semantik murni, lolos validasi WCAG 2.2 Level AA, dan mendukung interoperabilitas downstream parsers.

#### 2. Requirements & Technical Constraints
- **Semantic Tags Requirements**: Wajib menggunakan elemen `<kbd>`, `<samp>`, `<code>`, `<var>`, `<time>`, `<data>`, `<del>`, `<ins>`, `<mark>`, `<ruby>`, `<rt>`, `<rp>`, `<abbr>`, `<q>`, `<wbr>`, dan `<bdi>`.
- **Lokalisasi & Skrip (BiDi/CJK)**: 
  - Wajib menyertakan penandaan BCP 47 language tags yang presisi pada setiap segmen kalimat yang berganti bahasa.
  - Komentar multi-bahasa yang mengandung teks RTL dan ID alfanumerik (misal: CVE number atau hash commit) harus diisolasi secara sempurna agar tanda baca dan alfanumerik tidak mengalami *bidi visual corruption*.
  - Istilah teknis Jepang (misal: "仮想化" - virtualisasi) harus memiliki anotasi `<ruby>` dengan fallback `<rp>` yang valid.
- **Tipografi Teknis**:
  - Angka metrik finansial/sistemik harus menggunakan penandaan semantik yang tepat dan terisolasi dari *layout shift*.
  - Pemotongan kata (*word break*) pada jalur file (path) panjang yang tidak beraturan harus didefinisikan secara semantik tanpa menyisipkan spasi visual yang merusak eksekusi terminal saat disalin.
- **Aksesibilitas**: Mutasi teks (`<del>` dan `<ins>`) wajib memiliki representasi tekstual yang terbaca oleh screen reader tanpa mengandalkan styling visual coret/garis bawah semata.

#### 3. Expected Output
Sajikan satu dokumen HTML fragment (atau dokumen lengkap mandiri) yang valid, bersih, tanpa framework CSS/JS eksternal (cukup semantik HTML murni dengan inline-CSS minimal khusus tipografi OpenType jika diperlukan), yang merepresentasikan skenario audit log teknis di atas secara komprehensif.

```html
<!-- Tuliskan solusi implementasi dokumen Anda di sini secara lengkap -->
```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda sebelum melangkah ke bab arsitektur DOM tingkat lanjut berikutnya.

### Saya harus memahami:
- [ ] Perbedaan fundamental antara *visual typography* (CSS) dan *semantic typography* (HTML5 Text-Level Semantics).
- [ ] Cara kerja Unicode Bidirectional Algorithm (UBA) dan bagaimana browser menyelesaikan directional runs pada teks campuran LTR dan RTL.
- [ ] Perbedaan fungsional dan parsing antara `<bdi>` (Bidirectional Isolation) dan `<bdo>` (Bidirectional Override).
- [ ] Atribut standar waktu mesin pada elemen `<time>` (ISO 8601, durasi, zona waktu, minggu, tahun/bulan).
- [ ] Model konten dan parsing tree dari anotasi fonetik `<ruby>`, `<rt>`, dan fallback mechanism `<rp>`.
- [ ] Algoritma penentuan tanda kutip hierarkis pada elemen `<q>` berdasarkan atribut bahasa leluhur (*ancestor language tag*).
- [ ] Peran spesifikasi BCP 47 (`lang="zh-Hans"`, `lang="ar-EG"`, `lang="en-US"`) dalam pemilihan glyph font OpenType dan aturan pemenggalan kata (*hyphenation/line-breaking*).
- [ ] Keterbatasan Accessibility Tree pada elemen teks mutasi (`<s>`, `<del>`, `<ins>`) dan strategi mitigasinya.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar kode subtags registri IANA Language Subtag (cukup mengetahui cara membaca format language-script-region seperti `sr-Latn-RS`).
- [ ] Tabel heksadesimal lengkap Unicode BiDi Control Characters (misal: `U+200E` LRM, `U+200F` RLM, `U+2066` LRI, `U+2067` RLI, `U+2069` PDI) karena engine HTML modern menyediakan abstraksi `<bdi>` dan `dir="auto"`.
- [ ] Nilai spesifik string representasi durasi kompleks ISO 8601 (cukup pahami sintaks dasar format `P...T...` seperti `P1DT12H`).

### Saya harus bisa melakukan:
- [ ] Melakukan isolasi terhadap User-Generated Content (UGC) multi-bahasa yang tidak terduga untuk mencegah kerusakan visual BiDi menggunakan `<bdi>` dan `dir="auto"`.
- [ ] Mengonstruksi dokumentasi sistem teknis/CLI yang kaya menggunakan sinergi terstruktur dari `<pre>`, `<code>`, `<kbd>`, `<samp>`, dan `<var>`.
- [ ] Mengimplementasikan teks angka tabular yang stabil dan bebas layout jitter menggunakan elemen `<data>` atau `<time>` yang dipadukan dengan properti OpenType CSS.
- [ ] Menulis markup perubahan status data (`<del>` dan `<ins>`) yang sepenuhnya aksesibel untuk assistive technology dengan menyertakan teks kontekstual yang ramah screen reader.
- [ ] Merancang markup multi-bahasa yang mematuhi standar tipografi CJK (menggunakan `<ruby>`, `<rt>`, `<rp>`, serta penanganan pemecahan baris via `<wbr>`).