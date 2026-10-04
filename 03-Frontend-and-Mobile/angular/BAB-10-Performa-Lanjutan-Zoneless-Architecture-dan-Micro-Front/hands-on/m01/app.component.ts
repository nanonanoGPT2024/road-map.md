Dalam arsitektur Zoneless, Angular mengeliminasi ketergantungan ini sepenuhnya. Mekanismenya diatur oleh antarmuka `ChangeDetectionScheduler`:
1.  **Notification Pipeline**: Ketika primitive reactive (seperti `WritableSignal`, method `markForCheck()`, atau template event listener bawaan Angular) mengalami interaksi, primitive tersebut memanggil `ChangeDetectionScheduler.notify()`.
2.  **Scheduler Coalescing**: Scheduler Angular mengumpulkan (*batching*) beberapa notifikasi ke dalam satu siklus microtask browser menggunakan `queueMicrotask()` atau `requestAnimationFrame()`.
3.  **Application Ref Synchronization**: Scheduler secara eksplisit mengeksekusi sinkronisasi tampilan hanya pada view-view yang memiliki flag `Consumer` kotor (`LView` flags).

### Module Federation: Anatomi Runtime Loading
Webpack Module Federation bekerja dengan membagi bundling ke dalam tiga komponen dasar:
1.  `remoteEntry.js`: Manifest kecil yang berisi tabel pemetaan (*manifest table*) chunk JavaScript, modul yang diekspos (*exposes*), dan kebutuhan dependensi bersama (*shared dependencies*).
2.  `Container Controller`: Objek global (`window.<remoteScope>`) yang diinisialisasi oleh `remoteEntry.js`, memiliki antarmuka standar:
    *   `init(sharedScope)`: Melakukan inisialisasi namespace modul bersama dan melakukan resolusi versi (semantic versioning fallback).
    *   `get(moduleName)`: Mengembalikan factory function untuk instantiation modul yang diminta.
3.  `Shared Scope Matrix`: Registry singleton runtime (`__webpack_share_scopes__.default`) tempat aplikasi Host dan Remote mendaftarkan library seperti `@angular/core`. Jika versi kompatibel, instance di memori akan dipakai bersama; jika tidak kompatibel, fallback isolated chunk akan di-load secara dinamis.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Zoneless Reactivity Graph & Signal Dependency Tracking
Secara internal di `@angular/core`, Signal diimplementasikan menggunakan arsitektur **Push/Pull Directed Acyclic Graph (DAG)**.

1.  **Node Types**:
    *   *Producer*: Signal yang menyimpan nilai mutabel (`WritableSignal`) atau turunan (`ComputedSignal`).
    *   *Consumer*: Konteks reaktif yang membaca producer, seperti `effect()` atau template rendering expression node (`ReactiveLViewConsumer`).
2.  **Fase Push (Dirtiness Propagation)**:
    Ketika Anda memanggil `.set()` atau `.update()` pada sebuah Signal:
    *   Producer mengiterasi seluruh daftar Consumer yang mencatatnya sebagai dependensi.
    *   Producer mengirimkan sinyal status "Dirty" (hanya satu bit flag) ke Consumer.
    *   Pada tahap ini, **tidak ada kalkulasi nilai baru**. Yang ditransmisikan hanyalah invalidasi status.
3.  **Fase Pull (Lazy Evaluation)**:
    Ketika scheduler Angular mencapai giliran eksekusi frame DOM:
    *   Renderer membaca Consumer yang kotor.
    *   Consumer secara rekursif meminta (*pull*) nilai terbaru dari Producer.
    *   Jika Producer adalah `computed()`, ia hanya mengevaluasi ulang logikanya jika nilai producer hulu (*upstream*) benar-benar telah berubah nilainya (`===` atau custom equality checker).

### Webpack Module Federation: Dynamic Host-Remote Resolution
Dalam arsitektur micro-frontend dinamis, URL Remote tidak boleh di-*hardcode* pada build time. Kita menggunakan arsitektur **Dynamic Remote Manifest**:
1. Host memuat file konfigurasi runtime `manifest.json`.
2. Angular Router membaca manifest tersebut dan mengonfigurasi jalur routing secara dinamis menggunakan `loadChildren` atau `loadComponent`.
3. Komponen federasi dimuat secara asinkron (*lazy chunk*). Seluruh siklus Dependency Injection (DI) Angular pada remote dipetakan sebagai anak (*child injector*) dari Host root injector, atau terisolasi penuh melalui *EnvironmentInjector* mandiri.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan nyata: aplikasi zoneless mandiri (*standalone*) yang mengimplementasikan fine-grained reactivity.

### 1. Inisialisasi Zoneless Application (`main.ts`)
