# BAB 01 — Quiz dan Challenge

Bagian ini bertujuan untuk menguji pemahaman Anda mengenai fondasi inti React, JSX, dan React Fiber Engine yang telah dibahas pada modul-modul sebelumnya.

---

## A. Soal Basic (Konsep Inti)

1. **Apa perbedaan utama antara Real DOM dan Virtual DOM dalam konteks React?**
   Jelaskan mengapa React memilih untuk menggunakan arsitektur Virtual DOM alih-alih memanipulasi Real DOM secara langsung pada setiap perubahan state.

2. **Apa yang dimaksud dengan JSX?**
   Apakah browser secara langsung memahami JSX? Jelaskan proses transformasi (transpilation) yang terjadi sebelum kode dapat dieksekusi di browser.

3. **Mengapa atribut `class` pada elemen HTML ditulis sebagai `className` di dalam JSX?**
   Berikan alasan teknis di balik penamaan ini.

4. **Apa itu komponen (Component) di React?**
   Jelaskan perbedaan mendasar antara Function Component dan Class Component secara konseptual.

5. **Apa fungsi dari `React.createElement`?**
   Bagaimana hubungannya dengan sintaks deklaratif yang biasa kita tulis menggunakan JSX?

---

## B. Soal Intermediate (Mekanisme Internal & Troubleshooting)

1. **Bagaimana algoritma Reconciliation (Diffing) bekerja pada React?**
   Jelaskan secara garis besar bagaimana React membandingkan pohon Virtual DOM lama dan baru untuk menentukan perubahan apa yang harus diterapkan pada Real DOM.

2. **Apa peran kunci (key) `prop` saat merender list di React?**
   Jelaskan masalah apa yang mungkin terjadi jika Anda menggunakan indeks (index) array sebagai nilai `key` saat item list dapat diubah urutannya atau dihapus.

3. **Apa itu React Fiber?**
   Jelaskan masalah pada arsitektur Stack Reconciler sebelumnya yang diselesaikan oleh React Fiber Engine.

4. **Dalam konteks arsitektur Fiber, jelaskan perbedaan antara "Render Phase" dan "Commit Phase"!**
   Fase manakah yang dapat diinterupsi (interruptible) dan mengapa hal tersebut penting untuk performa UI?

5. **Troubleshooting:**
   Anda memiliki sebuah komponen kompleks dengan daftar ribuan elemen. Saat Anda mengetik di sebuah input text di luar list, seluruh list ikut ter-render ulang, membuat antarmuka terasa sangat laggy.
   Berdasarkan pengetahuan Anda tentang rendering React, sebutkan penyebab potensial dari render tak terduga ini dan strategi konseptual apa yang bisa memecahkannya.

---

## C. Skenario Kasus Nyata Produksi

1. **Skenario 1: Widget Real-Time Ticker**
   Anda membangun widget dashboard saham yang menampilkan harga real-time yang berubah setiap milidetik. Anda menyadari bahwa menggunakan pendekatan state standard membuat main thread kewalahan dan browser macet.
   *Bagaimana Anda mendesain arsitektur rendering untuk komponen ini agar tidak membebani Fiber Reconciler dan menjaga aplikasi tetap responsif?*

2. **Skenario 2: Migrasi Arsitektur Lama**
   Tim Anda mewarisi proyek dengan banyak file `script.js` yang menyuntikkan HTML string langsung ke dalam `innerHTML` dari berbagai kontainer DOM. Anda ditugaskan memperkenalkan React secara perlahan ke dalam sistem ini (Incremental Adoption).
   *Bagaimana strategi awal yang tepat untuk mulai mengganti bagian-bagian kecil tersebut dengan React tanpa perlu me-rewrite total aplikasi menjadi Single Page Application (SPA)?*

3. **Skenario 3: Debugging Hydration Mismatch**
   Aplikasi Server-Side Rendering (SSR) yang baru di-deploy sering mengalami peringatan: *"Text content did not match. Server: '08:15 AM' Client: '08:15:30 AM'"*. Hal ini membuat React membuang DOM dari server dan me-render ulang sepenuhnya.
   *Mengapa hal ini terjadi dalam konteks hydration dan eksekusi rendering awal? Bagaimana cara mencegah mismatch semacam ini pada elemen dinamis seperti waktu saat ini?*

---

## D. Chapter Challenge

**Membangun Mock Render Tree Analyzer**

**Objective:**
Anda diminta untuk secara konseptual merancang struktur data (tanpa perlu menulis kode React sesungguhnya, cukup rancangan data atau pseudocode) yang meniru bagaimana Fiber node saling berhubungan dalam sebuah tree.

**Requirement & Constraints:**
1. Rancanglah object JavaScript yang merepresentasikan satu `FiberNode`.
2. Pastikan properti tersebut memiliki pointer/referensi untuk merepresentasikan struktur tree yang *interruptible*, yaitu:
   - `child` (anak pertama)
   - `sibling` (saudara kandung berikutnya)
   - `return` (orang tua)
3. Buatlah hierarki contoh sederhana yang merepresentasikan struktur komponen:
   ```jsx
   <App>
      <Header />
      <Sidebar />
      <Content />
   </App>
   ```
4. Telusuri (traverse) struktur data yang Anda buat menggunakan pola loop (bukan rekursif) untuk menyimulasikan bagaimana Fiber Work Loop memproses setiap node.

*Catatan: Tidak ada jawaban benar tunggal. Fokuslah pada pemahaman bagaimana linked list digunakan untuk menggantikan recursion call stack standar.*

---

## E. Knowledge Check & Checklist

### Saya harus memahami
- Konsep dasar React (Virtual DOM, Komponen, Deklaratif UI).
- Proses transformasi JSX menjadi pemanggilan fungsi JavaScript murni.
- Mengapa dan bagaimana algoritma Diffing / Reconciliation React bekerja.
- Motivasi di balik arsitektur React Fiber (Interruptible rendering, prioritas kerja).
- Pemisahan siklus kerja React menjadi Render Phase dan Commit Phase.

### Saya tidak perlu menghafal
- Implementasi source code React secara persis bit-by-bit.
- Algoritma diffing kompleks untuk kasus langka (cukup pahami prinsip heuristiknya).
- Setiap sintaks Babel plugin yang menangani JSX.

### Saya harus bisa melakukan
- Menulis struktur JSX yang benar dengan atribut valid (mis. `className`, penutupan tag).
- Menentukan penggunaan `key` yang tepat pada list statis maupun dinamis.
- Menganalisa mengapa sebuah komponen mungkin me-render berlebihan (konsep awal).

### Checklist

- [ ] Memahami konsep Virtual DOM
- [ ] Memahami cara kerja JSX
- [ ] Bisa membuat komponen dasar
- [ ] Bisa menjelaskan algoritma Reconciliation secara high-level
- [ ] Memahami arsitektur Fiber dan fase rendering
- [ ] Memahami trade-off pembaruan State secara langsung vs Virtual DOM
- [ ] Bisa menerapkan dalam real-world scenario sederhana
