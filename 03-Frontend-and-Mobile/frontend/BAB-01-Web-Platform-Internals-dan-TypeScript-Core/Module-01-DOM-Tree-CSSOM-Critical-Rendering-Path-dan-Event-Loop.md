# DOM Tree, CSSOM, Critical Rendering Path, & JavaScript Event Loop Internals

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

- **Menjelaskan** struktur internal DOM Tree dan CSSOM sebagai representasi memori dari dokumen HTML/CSS, termasuk node types, tree traversal, dan inheritance chain
- **Mendeskripsikan** setiap fase Critical Rendering Path (CRP) — Parse → Style → Layout → Paint → Composite — beserta bottleneck yang mungkin terjadi di setiap fase
- **Mengidentifikasi** operasi yang memicu reflow, repaint, dan compositing, serta menjelaskan dampak performa masing-masing
- **Menjelaskan** mekanisme JavaScript Event Loop secara presisi: Call Stack, Web APIs, Callback Queue, Microtask Queue, dan Render Steps
- **Mendiagnosis** permasalahan performa rendering menggunakan Chrome DevTools (Performance tab, Layers panel, Rendering panel)
- **Membangun** komponen UI yang menghindari layout thrashing, mengoptimalkan paint area, dan memanfaatkan GPU compositing layer secara tepat
- **Menulis** kode asinkron yang memahami perbedaan eksekusi microtask vs macrotask dan dampaknya terhadap rendering frame

---

## 2. Prerequisite

Sebelum melanjutkan modul ini, pastikan Anda telah memahami:

| Konsep | Level yang Dibutuhkan | Referensi |
|---|---|---|
| HTML semantik dasar | Paham struktur tag, nesting, atribut | MDN: HTML Basics |
| CSS selector, specificity, box model | Paham cascade dan inheritance | MDN: CSS Specificity |
| JavaScript ES6+ fundamentals | Paham function, closure, Promise, async/await | MDN: JavaScript Guide |
| Konsep synchronous vs asynchronous | Paham callback dan Promise chaining | MDN: Asynchronous JS |
| Browser developer tools dasar | Bisa membuka Console dan Elements tab | Chrome DevTools Docs |

> **Catatan Penting:** Modul ini bersifat *internals-first* — kita akan membedah cara kerja browser di level mesin, bukan sekadar API yang tersedia. Pemahaman ini adalah fondasi untuk semua optimasi performa frontend.

---

## 3. Concept

### 3.1 Gambaran Besar: Browser sebagai Mesin Rendering

Browser modern adalah salah satu perangkat lunak paling kompleks yang pernah dibuat manusia. Ketika Anda mengetikkan URL dan menekan Enter, serangkaian proses rumit terjadi dalam hitungan milidetik. Memahami proses ini bukan sekadar akademis — ini adalah perbedaan antara aplikasi yang terasa *instant* dan aplikasi yang terasa *lambat*.

Tiga pilar utama yang akan kita pelajari:

```
┌─────────────────────────────────────────────────┐
│              BROWSER RENDERING ENGINE            │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ DOM Tree │  │  CSSOM   │  │  Event Loop   │  │
│  │ (Struktur│  │  (Style) │  │  (Eksekusi JS)│  │
│  │  Dokumen)│  │          │  │               │  │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘  │
│       │             │                │           │
│       └──────┬──────┘                │           │
│              ▼                       │           │
│      ┌───────────────┐               │           │
│      │ Render Tree   │◄──────────────┘           │
│      │ (DOM + CSSOM) │                           │
│      └───────┬───────┘                           │
│              ▼                                   │
│      Critical Rendering Path                     │
│      Layout → Paint → Composite                  │
└─────────────────────────────────────────────────┘
```

### 3.2 DOM Tree: Representasi Memori Dokumen

DOM (Document Object Model) adalah **representasi berorientasi objek** dari dokumen HTML yang dibuat oleh browser di memori. Ini bukan HTML itu sendiri — ini adalah *interpretasi* browser terhadap HTML, direpresentasikan sebagai pohon node yang dapat dimanipulasi via JavaScript.

**Proses Parsing HTML menjadi DOM:**

```
Bytes → Characters → Tokens → Nodes → DOM Tree
```

1. **Bytes:** Browser menerima raw bytes dari jaringan
2. **Characters:** Bytes dikonversi ke karakter berdasarkan encoding (UTF-8)
3. **Tokens:** HTML Tokenizer memecah karakter menjadi token (`StartTag`, `EndTag`, `Character`, `Comment`, dll.)
4. **Nodes:** Setiap token dikonversi menjadi node object
5. **DOM Tree:** Node-node diorganisir dalam struktur pohon berdasarkan hierarki

**Node Types dalam DOM:**

```javascript
// Node.ELEMENT_NODE = 1
// Node.TEXT_NODE = 3
// Node.COMMENT_NODE = 8
// Node.DOCUMENT_NODE = 9
// Node.DOCUMENT_TYPE_NODE = 10
// Node.DOCUMENT_FRAGMENT_NODE = 11

document.nodeType;           // 9 (DOCUMENT_NODE)
document.body.nodeType;      // 1 (ELEMENT_NODE)
document.body.firstChild;    // Mungkin TEXT_NODE (whitespace!)
```

### 3.3 CSSOM: CSS Object Model

Paralel dengan DOM, browser juga membangun **CSSOM** — representasi pohon dari semua aturan CSS yang berlaku. CSSOM adalah *blocking* secara default karena browser tidak dapat merender konten tanpa mengetahui style yang berlaku.

**Proses Parsing CSS menjadi CSSOM:**

```
Bytes → Characters → Tokens → Rules → CSSOM Tree
```

CSSOM berbeda dari DOM dalam satu aspek krusial: **CSSOM tidak dapat dibangun secara incremental**. Browser harus memiliki *semua* CSS sebelum dapat membangun CSSOM, karena sebuah aturan CSS di bagian bawah stylesheet bisa mengoverride aturan di bagian atas.

**Cascade dan Specificity dalam CSSOM:**

CSSOM menyimpan *computed styles* — nilai final setelah mempertimbangkan:
1. Browser default styles (User Agent Stylesheet)
2. Author styles (CSS yang Anda tulis)
3. User styles (preferensi pengguna)
4. Inline styles
5. `!important` declarations

### 3.4 Critical Rendering Path (CRP)

CRP adalah urutan langkah yang harus diselesaikan browser sebelum konten pertama dapat ditampilkan ke layar.

```
HTML → DOM
CSS  → CSSOM
           ↓
      Render Tree
           ↓
        Layout
           ↓
         Paint
           ↓
       Composite
           ↓
        Screen
```

Setiap langkah memiliki karakteristik dan bottleneck tersendiri.

### 3.5 JavaScript Event Loop

Event Loop adalah mekanisme yang memungkinkan JavaScript — yang *single-threaded* — menangani operasi asinkron tanpa memblokir eksekusi. Ini bukan fitur JavaScript itu sendiri, melainkan fitur **runtime environment** (browser atau Node.js).

**Komponen utama Event Loop:**

```
┌─────────────────────────────────────────────────────┐
│                    CALL STACK                        │
│  ┌──────────────────────────────────────────────┐   │
│  │  main()                                      │   │
│  │  setTimeout callback                         │   │
│  │  Promise.then handler                        │   │
│  └──────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│                    WEB APIs                          │
│  setTimeout, fetch, DOM events, requestAnimationFrame│
├─────────────────────────────────────────────────────┤
│              MICROTASK QUEUE                         │
│  Promise callbacks, queueMicrotask, MutationObserver │
├─────────────────────────────────────────────────────┤
│              MACROTASK QUEUE (Task Queue)            │
│  setTimeout, setInterval, I/O, UI events             │
└─────────────────────────────────────────────────────┘
```

---

## 4. Why?

### Mengapa Harus Memahami DOM Tree Internals?

**Masalah yang dipecahkan:**

Tanpa memahami DOM internals, developer sering melakukan kesalahan seperti:

```javascript
// ❌ Tidak tahu bahwa ini membuat 1000 reflow
for (let i = 0; i < 1000; i++) {
  document.getElementById('list').innerHTML += `<li>${i}</li>`;
}

// ✅ Dengan pemahaman DOM, tahu cara yang benar
const fragment = document.createDocumentFragment();
for (let i = 0; i < 1000; i++) {
  const li = document.createElement('li');
  li.textContent = i;
  fragment.appendChild(li);
}
document.getElementById('list').appendChild(fragment);
```

Perbedaan performa: **~1000x lebih cepat** untuk 1000 item.

### Mengapa CSSOM Penting?

CSS yang tidak dioptimalkan dapat **memblokir rendering** secara keseluruhan:

```html
<!-- ❌ CSS eksternal memblokir rendering -->
<link rel="stylesheet" href="huge-library.css">

<!-- ✅ CSS kritis inline, sisanya deferred -->
<style>/* critical CSS */</style>
<link rel="stylesheet" href="non-critical.css" media="print" 
      onload="this.media='all'">
```

### Mengapa CRP Penting?

**First Contentful Paint (FCP)** dan **Largest Contentful Paint (LCP)** — dua Core Web Vitals yang mempengaruhi SEO dan user experience — sangat bergantung pada seberapa cepat CRP diselesaikan.

Data industri:
- **53% pengguna** meninggalkan halaman yang membutuhkan lebih dari 3 detik untuk load (Google, 2018)
- Setiap **100ms** peningkatan kecepatan = **1% peningkatan konversi** (Deloitte, 2020)

### Mengapa Event Loop Penting?

Tanpa memahami Event Loop, Anda akan menulis kode yang:
- Memblokir UI thread dan membuat halaman *unresponsive*
- Memiliki race condition yang sulit di-debug
- Mengeksekusi kode dalam urutan yang tidak terduga

```javascript
// Tanpa memahami Event Loop, ini terlihat aneh:
console.log('1');
setTimeout(() => console.log('2'), 0);
Promise.resolve().then(() => console.log('3'));
console.log('4');

// Output: 1, 4, 3, 2
// Mengapa? Karena microtask (Promise) lebih prioritas dari macrotask (setTimeout)
```

---

## 5. What?

### 5.1 DOM Tree — Definisi Presisi

**DOM (Document Object Model)** adalah:
- Standar W3C yang mendefinisikan antarmuka platform-neutral dan language-neutral untuk mengakses dan memanipulasi dokumen HTML/XML
- Representasi in-memory dari dokumen sebagai pohon node hierarkis
- API yang memungkinkan program dan skrip untuk mengakses dan mengubah konten, struktur, dan style dokumen secara dinamis

**Spesifikasi teknis DOM:**
- Didefinisikan oleh [WHATWG DOM Living Standard](https://dom.spec.whatwg.org/)
- Setiap node mengimplementasikan interface `Node`
- `Element` extends `Node`, `HTMLElement` extends `Element`, `HTMLDivElement` extends `HTMLElement`

**Interface Hierarchy:**

```
EventTarget
  └── Node
        ├── Document
        │     └── HTMLDocument
        ├── DocumentFragment
        ├── CharacterData
        │     ├── Text
        │     ├── Comment
        │     └── CDATASection
        └── Element
              └── HTMLElement
                    ├── HTMLDivElement
                    ├── HTMLInputElement
                    ├── HTMLButtonElement
                    └── ... (100+ spesifik elements)
```

### 5.2 CSSOM — Definisi Presisi

**CSSOM (CSS Object Model)** adalah:
- Kumpulan API yang memungkinkan manipulasi CSS dari JavaScript
- Representasi in-memory dari semua stylesheet yang berlaku
- Terdiri dari dua bagian utama: **CSS Rules** (aturan mentah) dan **Computed Styles** (nilai final per-element)

**Spesifikasi teknis CSSOM:**
- Didefinisikan oleh [CSSOM specification (W3C)](https://www.w3.org/TR/cssom-1/)
- `document.styleSheets` → `StyleSheetList`
- `CSSStyleSheet` → `CSSRuleList` → `CSSRule` (CSSStyleRule, CSSMediaRule, dll.)
- `window.getComputedStyle(element)` → `CSSStyleDeclaration`

### 5.3 Critical Rendering Path — Definisi Presisi

**CRP** adalah urutan langkah yang browser lakukan untuk mengkonversi HTML, CSS, dan JavaScript menjadi piksel di layar. Terdiri dari:

| Fase | Input | Output | Karakteristik |
|---|---|---|---|
| **Parse** | HTML bytes | DOM Tree | Incremental, dapat diinterupsi oleh script |
| **Style** | DOM + CSS | Render Tree | Blocking, membutuhkan complete CSSOM |
| **Layout** | Render Tree | Box Model geometry | CPU-intensive, triggers reflow |
| **Paint** | Layout + Styles | Paint records | GPU-intensive, triggers repaint |
| **Composite** | Paint layers | Frame pixels | GPU-only, paling murah |

### 5.4 JavaScript Event Loop — Definisi Presisi

**Event Loop** adalah mekanisme runtime yang:
- Terus-menerus memeriksa apakah Call Stack kosong
- Jika kosong, mengambil task dari queue dan memasukkannya ke Call Stack
- Memiliki prioritas: **Microtask Queue > Macrotask Queue**
- Terintegrasi dengan **Rendering Pipeline** browser (render steps terjadi antara macrotasks)

**Komponen spesifik:**

| Komponen | Definisi | Contoh |
|---|---|---|
| **Call Stack** | LIFO stack untuk eksekusi function | Function calls, synchronous code |
| **Heap** | Memory region untuk object allocation | `new Object()`, closures |
| **Web APIs** | Browser-provided async APIs | `setTimeout`, `fetch`, `addEventListener` |
| **Microtask Queue** | High-priority queue, dikuras sebelum render | `Promise.then`, `queueMicrotask`, `MutationObserver` |
| **Task Queue (Macrotask)** | Lower-priority queue |
