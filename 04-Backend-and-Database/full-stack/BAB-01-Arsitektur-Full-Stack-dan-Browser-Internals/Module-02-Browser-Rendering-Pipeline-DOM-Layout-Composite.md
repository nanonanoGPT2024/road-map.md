---
[⬅️ Module 01: Paradigma Render Web Modern](./Module-01-Paradigma-Render-SSR-CSR-SSG-ISR-Hydration.md) | [📋 Silabus Induk](../README.md) | [BAB 01 Quiz & Challenge ➡️](./BAB-01-Quiz-dan-Challenge.md)
---

# Module 02: Browser Critical Rendering Path, DOM/CSSOM, Layout, & GPU Compositing

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai arsitektur multi-proses browser modern (Chromium/Blink & WebKit): **Browser Process**, **Renderer Process**, **GPU Process**, dan **Network Service**.
- Memahami setiap tahapan **Critical Rendering Path (CRP)**: konversi *Bytes -> Tokens -> Nodes -> DOM/CSSOM Tree -> Render Tree -> Layout (Reflow) -> Paint (Rasterization) -> Composite*.
- Mengidentifikasi dan membasmi bencana performa **Forced Synchronous Layout (Layout Thrashing)** yang memicu frame drops (FPS di bawah 60).
- Membedakan properti CSS yang memicu **Reflow** (mahal), **Repaint** (sedang), dan properti yang murni ditangani oleh **GPU Compositor** (`transform`, `opacity`) (sangat murah, 120 FPS).
- Menerapkan teknik optimasi performa layout tingkat lanjut: atribut `contain: strict`, `content-visibility: auto`, dan penjadwalan animasi via `requestAnimationFrame` (rAF).

---

## 2. Prerequisite
- Memahami konsep dasar HTML DOM Tree dan selektor CSS.
- Pemahaman siklus Event Loop JavaScript (Microtasks vs Macrotasks) (Backend BAB 02).
- Pemahaman paradigma rendering SSR vs CSR (Modul 01).

---

## 3. Concept
Setiap kali sebuah halaman web dimuat, browser tidak sekadar "menggambar" teks dan warna di layar monitor. Browser adalah sistem operasi mikro yang menjalankan pipeline kompilasi dan kalkulasi geometris yang sangat kompleks.

Untuk menghasilkan animasi yang mulus tanpa patah-patah (*Jank-Free 60 FPS*), browser memiliki batas waktu maksimal **16.6 milidetik per frame** (atau **8.3 ms pada layar modern 120 Hz**). Di dalam jendela waktu yang sangat sempit tersebut, browser harus mengeksekusi kode JavaScript pengguna, menghitung ulang gaya visual, menentukan posisi koordinat setiap elemen di layar (*Layout / Reflow*), mengonversi kotak vektor menjadi piksel warna (*Paint*), dan mengirimkan lapisan grafis ke kartu grafis (*GPU Compositing*).

Seorang Principal Full-Stack Engineer harus memahami bagaimana setiap baris kode CSS dan JavaScript berinteraksi langsung dengan thread rendering browser.

---

## 4. Why?
Tanpa pemahaman arsitektur rendering browser:
1. **Layout Thrashing (Bencana 10 FPS):** Menulis perulangan JavaScript sederhana yang membaca `element.offsetHeight` lalu mengubah `element.style.top`, memaksa browser melakukan reflow berulang-ulang ratusan kali dalam satu frame hingga antarmuka macet total.
2. **Animasi Boros CPU:** Menggerakkan elemen popup menggunakan properti `top`, `left`, atau `margin`, yang memaksa CPU menghitung ulang layout seluruh halaman pada setiap frame alih-alih memanfaatkan akselerasi hardware GPU.
3. **Render-Blocking CSS & JS:** Menaruh tag `<script>` atau `<link rel="stylesheet">` pihak ketiga yang lambat di dalam tag `<head>` tanpa atribut `defer` atau `async`, menahan proses pembangunan DOM dan membekukan layar dalam kondisi putih kosong.
4. **Alokasi Layer Memori Berlebih (*Memory Layer Explosion*):** Menambahkan `will-change: transform` pada ribuan elemen sekaligus, membuat GPU kehabisan VRAM dan menyebabkan browser crash seketika di perangkat mobile.

---

## 5. What? (Tahapan Critical Rendering Path)

```
[ HTML Bytes ] ──▶ [ Tokenizer ] ──▶ [ DOM Tree ]
                                         │
                                         ▼
                                  [ RENDER TREE ] ──▶ [ LAYOUT / REFLOW ] ──▶ [ PAINT / RASTER ] ──▶ [ GPU COMPOSITE ] ──▶ [ LAYAR ]
                                         ▲             (Kalkulasi X, Y,        (Pikselasi Warna         (Penggabungan Layer
                                         │              Width, Height)          ke Bitmap Memory)        oleh GPU Processor)
[ CSS Bytes ]  ──▶ [ Tokenizer ] ──▶ [ CSSOM Tree ]
```

### A. Perbedaan Tahapan Pemrosesan:
1. **DOM Tree (Document Object Model):** Representasi struktur hierarki node HTML murni di memori.
2. **CSSOM Tree (CSS Object Model):** Representasi pohon aturan gaya yang telah dihitung (*Computed Styles*) berdasarkan aturan kaskade dan spesifisitas selektor.
3. **Render Tree:** Kombinasi antara DOM dan CSSOM yang **hanya memuat elemen yang benar-benar terlihat di layar**.
   - Node dengan `display: none` **TIDAK MASUK** ke dalam Render Tree.
   - Node dengan `visibility: hidden` **TETAP MASUK** ke dalam Render Tree (karena tetap memakan ruang fisik layout).
4. **Layout (Reflow):** Menghitung ukuran geometri pasti (*Bounding Box*) dan posisi koordinat $X, Y$ setiap kotak visual pada viewport.
5. **Paint (Rasterization):** Mengisi piksel visual: warna background, teks, border, bayangan (*box-shadow*), dan gambar ke dalam lapisan (*Layers*).
6. **Compositing:** GPU mengambil seluruh lapisan yang telah diraster dan menggabungkannya ke dalam frame buffer monitor.

---

## 6. How? (Tiga Tingkatan Biaya Properti CSS)

| Tingkat Operasi | Tahapan yang Dieksekusi | Contoh Properti CSS | Dampak Performa |
|---|---|---|---|
| **Level 1: Layout Trigger (Paling Mahal)** | JS -> Style -> **Layout** -> **Paint** -> **Composite** | `width`, `height`, `padding`, `margin`, `top`, `left`, `fontSize`, `display` | 🔴 Sangat Berat (CPU reflow seluruh DOM) |
| **Level 2: Paint Trigger (Menengah)** | JS -> Style -> ~~Layout~~ -> **Paint** -> **Composite** | `color`, `backgroundColor`, `boxShadow`, `visibility`, `borderRadius` | 🟡 Sedang (Tanpa reflow, tapi re-raster piksel) |
| **Level 3: Composite Trigger (Super Cepat)**| JS -> Style -> ~~Layout~~ -> ~~Paint~~ -> **Composite** | `transform` (`translate`, `scale`, `rotate`), `opacity`, `filter` | 🟢 **120 FPS Mulus (Dikerjakan murni oleh GPU)** |

---

## 7. Analogy
Bayangkan proses mencetak majalah mode:
- **Layout (Reflow) ibarat Menata Tata Letak Percetakan:** Mengatur ulang ukuran kolom teks dan posisi foto di halaman. Jika Anda mengubah ukuran satu foto di pojok kiri atas, seluruh paragraf di bawahnya harus digeser dan dihitung ulang letak nomor halamannya (**Sangat memakan waktu**).
- **Paint ibarat Menyemprotkan Tinta Warna:** Mengisi huruf dan kotak foto dengan tinta warna CMYK di atas kertas putih.
- **Composite ibarat Menumpuk Plastik Mika Transparan:** Majalah Anda dicetak pada 3 lembar plastik mika transparan terpisah (Lapisan Teks, Lapisan Foto Model, Lapisan Logo Sponsor). Jika Anda ingin menggeser logo sponsor ke kanan, Anda tidak perlu mencetak ulang foto model; Anda cukup menggeser lembar mika logo sponsor menggunakan tangan (**GPU Hardware Acceleration**).

---

## 8. Diagram: Fenomena Layout Thrashing (Reflow Loop)

```
KODE BURUK (LAYOUT THRASHING):
for (let i = 0; i < boxes.length; i++) {
  const width = boxes[i].offsetWidth; // 1. BACA Geometri (Memaksa browser Reflow seketika!)
  boxes[i].style.width = width + 10 + 'px'; // 2. TULIS Style (Menandai layout kotor / dirty!)
}
```

```
GRAFIK EKSEKUSI THREAD UTAMA (1 FRAME = 16.6 ms):
[ Read ] ──▶ [ REFLOW PAKSA ] ──▶ [ Write ] ──▶ [ Read ] ──▶ [ REFLOW PAKSA ] ──▶ [ Write ]
(Terjadi puluhan Reflow dalam 1 milidetik! Main Thread macet, FPS drop ke 5 FPS!)

KODE OPTIMAL (BATCH READ THEN BATCH WRITE):
// FASE 1: BACA SEMUA GEOMETRI (Batch Read)
const widths = boxes.map(b => b.offsetWidth); // Reflow hanya terjadi 1 kali!

// FASE 2: TULIS SEMUA GAYA (Batch Write)
boxes.forEach((b, i) => {
  b.style.width = widths[i] + 10 + 'px';
});
```

---

## 9. Simple Example: Deteksi Layout Thrashing & Perbaikan (JavaScript)

```javascript
// Antipattern: Forced Synchronous Layout
function resizeAllCardsBad(cards) {
  console.time('Bad Resize (Thrashing)');
  for (let i = 0; i < cards.length; i++) {
    // Membaca offsetHeight memaksa browser menghitung layout saat itu juga!
    const height = cards[i].offsetHeight;
    cards[i].style.height = (height + 5) + 'px';
  }
  console.timeEnd('Bad Resize (Thrashing)');
}

// Best Practice: Pisahkan Fase Baca dan Tulis (DOM Read/Write Batching)
function resizeAllCardsGood(cards) {
  console.time('Good Resize (Batched)');
  
  // 1. Batch Read
  const currentHeights = cards.map(card => card.offsetHeight);
  
  // 2. Batch Write menggunakan requestAnimationFrame agar selaras dengan refresh monitor
  requestAnimationFrame(() => {
    cards.forEach((card, index) => {
      card.style.height = (currentHeights[index] + 5) + 'px';
    });
  });
  
  console.timeEnd('Good Resize (Batched)');
}
```

---

## 10. Practical Example: Animasi 120 FPS dengan GPU Layer Promotion

```css
/* ANTIPATTERN: Memicu Reflow & Paint pada setiap frame animasi (Jank) */
.bad-modal-slide {
  position: absolute;
  top: 0;
  transition: top 0.3s ease-out; /* MEMICU REFLOW LEVEL 1! */
}
.bad-modal-slide.open {
  top: 300px;
}

/* BEST PRACTICE: Murni ditangani oleh GPU Compositor (Zero Reflow, Zero Repaint) */
.good-modal-slide {
  position: absolute;
  top: 0;
  will-change: transform; /* Memberitahu browser untuk mempromosikan elemen ke GPU Layer terpisah */
  transform: translateY(0);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.good-modal-slide.open {
  transform: translateY(300px); /* 100% GPU COMPOSITE! */
}
```

---

## 11. Real World Example: Optimalisasi Scroll Feed Twitter / X dengan `content-visibility`

Pada linimasa media sosial dengan ribuan postingan feed:
- Memuat 1.000 cuitan tweet ke dalam DOM membuat browser harus menghitung layout koordinat untuk seluruh 1.000 elemen, memakan waktu 800 ms CPU.
- Tim engineer menerapkan properti CSS modern:
  ```css
  .tweet-card {
    content-visibility: auto;
    contain-intrinsic-size: 0 120px; /* Estimasi tinggi kartu tweet */
  }
  ```
- **Cara Kerja:** Browser secara cerdas **melewatkan tahapan Layout dan Paint** untuk seluruh kartu cuitan yang berada di luar layar viewport pengguna (*Off-screen*). Browser hanya merender elemen saat pengguna mendekati area scroll.
- Hasil: Waktu render awal linimasa turun dari **850 ms menjadi 12 ms** (**peningkatan performa 70x lipat**).

---

## 12. Trade-offs

| Teknik Optimasi | Keuntungan Performa | Biaya / Trade-off | Risiko Kesalahan |
|---|---|---|---|
| **GPU Layer Promotion (`will-change`)**| Animasi 60-120 FPS mulus | Memakan VRAM GPU tambahan | *Layer Explosion*: Browser crash jika dipasang di terlalu banyak elemen |
| **CSS `content-visibility: auto`** | Render awal instan, hemat CPU | Scrollbar bisa sedikit melompat jika ukuran intrinsik tidak akurat | Estimasi `contain-intrinsic-size` wajib presisi |
| **DOM Virtualization (TanStack Virtual)**| Mampu menampilkan 100.000 baris tabel | Kompleksitas kode JavaScript tinggi | Navigasi keyboard dan pencarian `Ctrl+F` di browser bawaan tidak bekerja |

---

## 13. When To Use
- **Gunakan `transform` dan `opacity`:** Untuk **100% animasi antarmuka** (transisi modal, sliding sidebar, dropdown menu, animasi drag-and-drop).
- **Gunakan `requestAnimationFrame` (rAF):** Saat membaca dan memperbarui gaya visual DOM secara dinamis menggunakan JavaScript.
- **Gunakan `content-visibility: auto`:** Pada daftar konten panjang (artikel blog panjang, kolom komentar dengan ratusan baris, katalog produk scrollable).

---

## 14. When NOT To Use
- **Jangan Pasang `will-change: transform` di File CSS Global (`* { will-change: ... }`):** Ini akan memaksa browser mengalokasikan buffer kartu grafis untuk setiap div di halaman, membuat memori GPU habis seketika (*Out of VRAM*). Pasang hanya pada elemen aktif saat animasi berlangsung!
- **Jangan Gunakan JavaScript untuk Animasi Sederhana:** Menggunakan perulangan `setInterval` atau `setTimeout` untuk mengubah koordinat elemen adalah praktik kuno yang tidak tersinkronisasi dengan refresh rate monitor (*V-Sync*). Gunakan CSS Transitions atau Web Animations API (WAAPI)!

---

## 15. Common Mistakes
1. **Membaca Geometri Setelah Menulis Gaya (Layout Thrashing):** Menjalankan kode `element.style.color = 'red'; console.log(element.offsetWidth); element.style.margin = '5px';`.
2. **Animasi `box-shadow` Langsung:** Menggerakkan `box-shadow: 0 10px 20px rgba(0,0,0,0.5)` memicu kalkulasi pikselasi Gaussian Blur yang sangat berat pada CPU. **Solusi:** Buat pseudo-element `::after` dengan bayangan statis dan animasikan `opacity`-nya via GPU!
3. **Mengabaikan Passive Event Listeners:** Menambahkan event listener scroll tanpa parameter `{ passive: true }`: `window.addEventListener('scroll', fn, { passive: true })`. Tanpa passive listener, browser menahan proses scroll untuk menunggu apakah JavaScript memanggil `e.preventDefault()`.

---

## 16. Best Practices

### Must Have
- Gunakan hanya **`transform` dan `opacity`** untuk menciptakan animasi antarmuka 60-120 FPS.
- Selalu tambahkan `{ passive: true }` pada event listener `scroll`, `touchstart`, dan `touchmove`.
- Pisahkan pembacaan DOM (*Reads*) dari penulisan DOM (*Writes*) dalam fungsi JavaScript yang memanipulasi banyak elemen.

### Recommended
- Gunakan tool audit performa seperti **Lighthouse** dan tab **Performance / Rendering** di Chrome DevTools untuk memantau *Layout Shift Regions* dan *Paint Flashing*.
- Manfaatkan CSS Containment (`contain: layout style paint`) pada komponen independen (seperti widget cuaca atau iklan pihak ketiga) agar reflow internal tidak menyebar ke seluruh halaman.

### Advanced
- Gabungkan **Web Animations API (WAAPI)** dengan *Composite Thread Animations* untuk menciptakan timeline animasi kompleks yang berjalan lancar bahkan saat main thread JavaScript sedang sibuk mengeksekusi komputasi berat.

---

## 17. Troubleshooting

| Masalah Performa | Indikasi Gejala | Langkah Investigasi | Tindakan Koreksi |
|---|---|---|---|
| **Animasi Patah-Patah (Frame Drops / Jank)** | FPS monitor turun ke 20-30 FPS saat scroll atau buka modal | Buka Chrome DevTools -> tab Performance -> cari bilah merah (*Long Task*) | Ganti properti `top/left/height` dengan `transform: translate3d()`, pisahkan layer dengan `will-change` |
| **Peringatan: `[Violation] Forced reflow while executing JavaScript`** | Log konsol menampilkan warning reflow paksa | Klik link baris kode pada warning di konsol | Batch seluruh operasi baca properti DOM di atas, lalu eksekusi operasi tulis di dalam rAF |
| **Tampilan Elemen Buram / Pecah saat Animasi** | GPU meraster elemen pada resolusi awal sebelum diskalakan | Periksa transformasi `scale()` pada teks | Gunakan resolusi aset yang lebih tinggi atau hindari pembesaran skala ekstrem |

---

## 18. Exercise
1. Bangun simulator Node.js yang memodelkan pipeline Critical Rendering Path: DOM Tree + CSSOM Tree -> Render Tree -> Layout Reflow -> Paint.
2. Simulasikan operasi Layout Thrashing (perulangan baca-tulis bersilangan) dan ukur penalti siklus komputasi yang dihasilkan.
3. Terapkan strategi DOM Batching dan buktikan reduksi kalkulasi layout hingga 90%!

---

## 19. Challenge
Rancang arsitektur komponen **Virtual Scroll Table** berkemampuan tinggi yang mampu menampilkan 500.000 baris data transaksi keuangan:
1. Rancang formula kalkulasi posisi viewport untuk hanya merender 25 baris yang sedang terlihat (*Windowing Technique*).
2. Terapkan CSS containment (`contain: strict`) dan akselerasi GPU `transform: translateY()` untuk menjamin scroll secepat kilat pada kecepatan 120 FPS tanpa layout thrashing!

---

## 20. Summary
Browser bukanlah kotak hitam misterius, melainkan mesin grafis yang bekerja berdasarkan hukum komputasi yang deterministik. Dengan menguasai setiap tahapan Critical Rendering Path, menghormati pembagian beban antara CPU Layout dan GPU Compositing, serta mengeliminasi Layout Thrashing, seorang Full-Stack Engineer mampu menciptakan pengalaman web yang secepat kilat, responsif, dan memberikan kesan premium bagi jutaan pengguna.

---
[⬅️ Module 01: Paradigma Render Web Modern](./Module-01-Paradigma-Render-SSR-CSR-SSG-ISR-Hydration.md) | [📋 Silabus Induk](../README.md) | [BAB 01 Quiz & Challenge ➡️](./BAB-01-Quiz-dan-Challenge.md)
---
