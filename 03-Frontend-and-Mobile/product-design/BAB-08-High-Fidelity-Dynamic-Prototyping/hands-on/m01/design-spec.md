---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 1–16:** Mengimpor `setup` dan `assign` dari modul `xstate` v5. Menyusun interface strongly-typed untuk `SwipeContext` dan `SwipeEvent`. Penentuan tipe ketat ini krusial untuk mencegah propagasi state invalid selama manipulasi data berkecepatan tinggi.
* **Baris 18–34:** Blok `setup` memisahkan implementasi concrete dari struktur state machine. Guard `hasExceededThreshold` mengevaluasi context secara deterministik; aksi `updatePosition` membatasi pergerakan negatif (`Math.max(0, params.deltaX)`) guna mencegah item terseret ke arah yang tidak diinginkan secara anatomis.
* **Baris 40–44:** Inisialisasi statechart dengan `initial: 'idle'` dan menetapkan threshold geser pada nilai terisolasi `160px`.
* **Baris 45–66:** State `tracking`. Menangani mutasi koordinat kontinu via event `POINTER_MOVE`. Pada event `POINTER_UP`, array transisi bersyarat dieksekusi: jika guard `hasExceededThreshold` terpenuhi, mesin berpindah ke state hierarkis `committing`; jika tidak, jatuh ke `springBack`.
* **Baris 67–70:** State `springBack` memanggil action `resetPosition` dan secara langsung (`always`) kembali ke `idle`, memicu pemulihan koordinat visual ke zero point.
* **Baris 71–89:** State hierarkis `committing`. Mengisolasi logika komunikasi asynchronous di bawah sub-state `persisting`. Jika gagal (`NETWORK_FAILURE`), mesin beralih ke sub-state `failed` tanpa merusak integritas state machine utama, memungkinkan antarmuka menampilkan pesan galat terisolasi dan menyediakan transisi pemulihan via event `RESET`.
* **Baris 90–92:** State terminal `dismissed`. Komponen mengidentifikasi bahwa siklus hidup item telah selesai dan dapat dilepas dari tree rendering secara aman.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: "Apex Trader" — High-Frequency Order Execution Drawer
*Apex Financial Corp* mengembangkan sistem perdagangan instrumen derivatif berkecepatan tinggi. Tim UX mendesain fitur krusial: **"Slide-to-Execute Market Order"** dengan visualisasi pergerakan harga bid-ask riil (*streaming ticks*) secara simultan.

### Masalah pada Prototyping Konvensional
1. **Desinkronisasi State UI:** Desainer membuat prototype Figma dengan smart animate, namun gagal memodelkan situasi saat harga berubah drastis (*price slippage*) di tengah-tengah gerakan geser pengguna.
2. **Frame Drops Parah:** Prototipe React awal memicu re-render seluruh root drawer pada setiap perubahan posisi pointer, menyebabkan frame rate anjlok hingga 18 FPS pada perangkat iPad Pro penguji saat canvas charting me-render candle data secara paralel.
3. **Ketiadaan Simulasi Gangguan Jaringan:** Prototype tidak merefleksikan kegagalan transisi ketika order ditolak server (*partial fill* / *rejection limit*), sehingga eksekutif tidak menyadari kegagalan UX yang fatal pada handling status error saat rilis beta.

### Persyaratan Arsitektural Solusi
* Gestur kontinu diisolasi menggunakan motion value terkomputasi langsung pada hardware compositing layer.
* Alur eksekusi divalidasi oleh Finite State Machine deterministik yang menangani pembatalan order akibat slippage real-time.
* Mock Service Worker bertugas menyimulasikan round-trip latency jaringan lengkap dengan error rejection rate sebesar 20%.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi berikut menggunakan **React 18/19**, **TypeScript**, **Framer Motion**, dan **XState v5**.

### 1. Inisialisasi Mock Service Worker (MSW) Network Simulator
