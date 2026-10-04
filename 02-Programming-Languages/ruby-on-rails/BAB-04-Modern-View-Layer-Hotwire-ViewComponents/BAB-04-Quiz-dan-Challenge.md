# BAB 04: Quiz, Challenge, & Knowledge Check
**Modern View Layer, Hotwire & ViewComponents**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Diferensiasi Eksekusi Turbo Drive vs. Turbo Frame**  
   Secara arsitektural, jelaskan bagaimana Turbo Drive mengintersepsi navigasi standar dokumen HTML dibandingkan dengan isolasi konteks pada Turbo Frame! Bagaimana Rails merespons header HTTP `Turbo-Frame` pada level controller dan layout engine, serta apa dampak komputasionalnya terhadap siklus render view di sisi server?

2. **Taksonomi Hotwire: Kapan Turbo Stream Diperlukan Dibandingkan Turbo Frame?**  
   Analisis skenario di mana Turbo Frame gagal memenuhi kebutuhan UI dinamis sehingga Anda wajib beralih ke Turbo Stream! Jelaskan perbedaan mendasar antara model *pull-based navigation* milik Turbo Frame dan *push-based targeted mutation* milik Turbo Stream, baik melalui respons HTTP maupun via ActionCable WebSocket.

3. **Mental Model Stimulus: State Management vs. DOM sebagai Single Source of Truth**  
   Berbeda dengan framework reaktif berbasis virtual DOM (seperti React atau Vue) yang mengelola *in-memory state tree*, Stimulus mengadopsi filosofi *"HTML-centric state"*. Jelaskan bagaimana konsep Values, Targets, dan Classes API pada Stimulus 3.x merefleksikan prinsip bahwa DOM adalah *Single Source of Truth*! Apa implikasinya terhadap arsitektur aplikasi Rails secara keseluruhan?

4. **Paradigma ViewComponent vs. Rails ActionView Partial**  
   GitHub mengembangkan `ViewComponent` untuk mengatasi kelemahan mendasar ActionView partials. Bandingkan kedua pendekatan tersebut dari perspektif:
   * Alokasi memori (*object allocation overhead*).
   * Enkapsulasi ruang lingkup (*variable scope leakage* dan penggunaan global helper).
   * Kemampuan pengujian terisolasi (*unit-level testing isolation* tanpa full rendering context).

5. **Turbo 8 Page Refresh & DOM Morphing (Idiomorph)**  
   Turbo 8 memperkenalkan paradigma *morphing* menggunakan algoritma Idiomorph untuk penyegaran halaman via Turbo Streams broadcast. Jelaskan bagaimana mekanisme rekonsiliasi DOM bekerja saat menerima payload HTML baru! Mengapa pendekatan ini secara radikal menyederhanakan kode view dibandingkan manipulasi granular DOM via Turbo Streams aksi klasik (`append`, `prepend`, `replace`, `update`)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mitigasi Memory Leak pada Stimulus Controller Lifecycle**  
   Perhatikan skenario di mana sebuah Stimulus controller menginisialisasi pustaka eksternal (misalnya instance Chart.js atau observer `IntersectionObserver` / `ResizeObserver`) di dalam method `connect()`. Jika elemen pembungkus controller tersebut diganti atau dihapus oleh aksi Turbo Streams atau Turbo Frame, jelaskan kegagalan siklus hidup yang dapat memicu *memory leak* di browser dan bagaimana implementasi method `disconnect()` yang strictly idempotent!

2. **Turbo Frame Breakout & Mekanisme Redirection Edge Cases**  
   Sebuah formulir autentikasi berada di dalam tag `<turbo-frame id="login_modal">`. Ketika user berhasil submit, controller mengembalikan `redirect_to dashboard_path`. Mengapa Turbo Frame memicu eror `Content missing` jika halaman dashboard tidak memiliki elemen `<turbo-frame id="login_modal">`? Jelaskan tiga strategi berbeda untuk menangani *frame breakout* ini, termasuk penggunaan atribut `data-turbo-frame="_top"`, header HTTP `Turbo-Location`, dan Turbo Stream actions!

3. **ActionCable Backplane Saturation & N+1 Broadcast Problem**  
   Dalam model Rails:
   ```ruby
   after_create_commit -> { broadcast_prepend_to "transactions" }
   ```
   Jika terjadi batch import 10.000 data transaksi via background job dalam hitungan detik, jelaskan *cascading failure* yang terjadi pada Redis Pub/Sub, thread worker ActionCable, dan performa browser klien! Bagaimana cara merancang pola broadcast yang aman menggunakan debouncing, background broadcasting (`broadcast_prepend_later_to`), atau agregasi data?

4. **Slots API & Sub-component Composition pada ViewComponent**  
   Jelaskan cara kerja internal API `renders_one` dan `renders_many` pada ViewComponent! Bagaimana mekanisme kompilasi template ViewComponent mengevaluasi slot secara lazy, dan apa konsekuensinya terhadap performa jika slot tersebut memerlukan query database tambahan di dalam blok eksekusinya?

5. **Turbo Morphing Conflict: State Desynchronization pada Form Input & Scroll Position**  
   Saat Turbo 8 melakukan *page morphing*, elemen input form yang sedang diisi oleh user atau status scroll kontainer tertentu dapat mengalami reset atau kedipan (*flicker*) jika tidak dikonfigurasi dengan benar. Jelaskan atribut apa saja yang disediakan oleh Turbo (`data-turbo-permanent`, `data-turbo-morph-action`, dll.) untuk memproteksi elemen DOM dari mutasi algoritma Idiomorph, serta bagaimana algoritma tersebut mempertahankan fokus elemen yang aktif!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Performa pada Live Bidding Engine (High-Concurrency Hotwire)
Platform lelang online skala enterprise menggunakan Rails 7.1 dengan Turbo Streams via ActionCable. Saat sebuah barang lelang populer memasuki 30 detik terakhir, terdapat 25.000 user yang terkoneksi ke channel `auction_123`. Setiap kali ada tawaran baru, server mengeksekusi render partial `_bid.html.erb` dan menyiarkannya (*broadcast*). 

**Masalah:**  
CPU server Rails melonjak ke 100%, latensi WebSocket meningkat drastis hingga 8 detik, dan sebagian user mengalami lag rendering parah di browser akibat ribuan mutasi DOM per menit.

**Pertanyaan Diagnostik & Solusi:**
1. Di mana letak bottleneck utama (CPU rendering vs. I/O network vs. browser DOM parsing)?
2. Bagaimana Anda mendesain ulang arsitektur broadcast ini? Evaluasi penggunaan Turbo 8 Page Refresh (Morphing) berbasis debounced ping vs. custom ActionCable message yang diproses oleh Stimulus controller secara client-side!
3. Jika tetap mempertahankan server-rendered HTML, optimasi apa yang wajib diterapkan pada layer view (misal: caching fragment pada level ViewComponent/partial sebelum broadcast)?

---

### Skenario B: Race Condition pada Optimistic UI & Concurrent Multi-Tab Updates
Sebuah sistem manajemen inventaris gudang menggunakan Turbo Frames untuk mengedit kuantitas stok barang secara inline. Operator A dan Operator B membuka halaman produk yang sama secara bersamaan di tablet masing-masing.

**Masalah:**
* Operator A menaikkan stok dari 10 ke 15 via Turbo Frame form inline.
* Sebelum request Operator A selesai di server, Operator B menekan tombol inline edit yang memicu fetch frame dari state lama (10).
* Klien Operator A menggunakan Stimulus untuk memanipulasi angka secara optimistik di UI.
* Terjadi *desynchronization*: Database mencatat nilai akhir Operator B (misal: 8), tetapi layar Operator A tetap menampilkan nilai optimistik 15, sementara Turbo Stream broadcast terlambat tiba dan ter-overwrite oleh rekonsiliasi frame lokal.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa memadukan *Optimistic UI* manual via Stimulus dengan server-driven Turbo Frame update rawan terhadap *race condition* inkonsistensi data?
2. Bagaimana Anda mengimplementasikan *Optimistic Locking* (`lock_version`) pada level ActiveRecord dan merefleksikannya ke dalam penanganan Turbo Frame error (HTTP 422 Unprocessable Content vs HTTP 409 Conflict)?
3. Rancang alur komunikasi di mana browser mendeteksi *stale state* dan menampilkan notifikasi visual untuk me-reload frame yang terdampak tanpa merusak form state user lain!

---

### Skenario C: Dilema Arsitektur: ViewComponent Monolith vs. React/Vue Micro-Frontend
Sebuah aplikasi SaaS FinTech memiliki dashboard analitik yang sangat kompleks: terdiri dari puluhan filter dinamis, tabel data dengan infinite scroll, grafik interaktif multi-layer, dan panel audit log real-time. Tim frontend mengusulkan penulisan ulang seluruh dashboard menggunakan React SPA, dengan alasan bahwa ActionView partials sudah menjadi "spaghetti code" yang lambat dan sulit diuji. Namun, tim backend ingin mempertahankan kesederhanaan arsitektur Rails monolith.

**Pertanyaan Diagnostik & Solusi:**
1. Sebagai Principal Architect, bagaimana Anda memetakan batas pemisahan tanggung jawab (*architectural boundaries*) menggunakan trio: **ViewComponent** (untuk representasi visual & rendering terisolasi), **Hotwire/Turbo** (untuk data transfer & navigasi), dan **Stimulus** (hanya untuk micro-interactions & bridging pustaka visualisasi pihak ketiga)?
2. Komponen apa dari dashboard tersebut yang mutlak membutuhkan Stimulus / pustaka JavaScript pihak ketiga (misalnya Canvas/WebGL charts), dan komponen mana yang 100% harus tetap dipertahankan sebagai server-rendered ViewComponent?
3. Buat perbandingan trade-off matriks (Network payload, Maintenance overhead, Time-to-Interactive, Testability) antara opsi:
   * **Opsi 1:** Full React SPA via Rails API.
   * **Opsi 2:** Modular ViewComponents + Hotwire + Stimulus-wrapped Chart components.

---

## 4. Chapter Challenge

### Tantangan Praktis: Real-Time Collaborative Financial Audit Matrix

#### Konteks & Problem Statement
Anda diminta membangun modul **Audit Trail & Adjustment Matrix** untuk sistem akuntansi enterprise. Modul ini memungkinkan beberapa akuntan publik melakukan penyesuaian nominal debit/kredit pada ratusan akun buku besar secara kolaboratif dalam satu layar secara real-time. Setiap perubahan harus langsung terekam, terisolasi per akun, dan menampilkan status *locked/editing* jika seorang akuntan sedang mengedit akun tersebut agar tidak terjadi tabrakan editing.

#### Requirements Teknis
1. **ViewComponent Architecture:**
   * Bangun `AuditMatrix::AccountRowComponent` menggunakan GitHub `ViewComponent`.
   * Komponen harus mendukung slots (`renders_one :action_buttons`, `renders_many :adjustment_history_entries`).
   * Component harus meng-cache rendering secara otomatis menggunakan fragment cache berbasis *cache key* model dan parameter izin user.
2. **Turbo Frame Editing & Breakout:**
   * Setiap baris akun (`AccountRowComponent`) harus dapat diubah menjadi mode form inline menggunakan Turbo Frame `<turbo-frame id="account_row_#{id}">`.
   * Form submission harus divalidasi di server; jika valid, update dikembalikan via Turbo Streams, jika tidak valid, respon HTTP 422 harus me-render ulang frame dengan pesan error tanpa merusak baris akun lainnya.
3. **Real-time Presence & Mutation via Turbo Streams & ActionCable:**
   * Saat Akuntan A mengklik "Edit" pada sebuah baris, Stimulus presence controller mengirim sinyal lock via WebSocket, sehingga baris akun tersebut di layar Akuntan B berubah tampilan menjadi status *Disabled/Locked by User A*.
   * Saat data disimpan, Turbo Stream me-broadcast pembaruan baris tersebut ke seluruh akuntan yang sedang membuka halaman tersebut, sekaligus memperbarui total kalkulasi neraca di bagian bawah layar.
4. **Stimulus Integration:**
   * Bangun `matrix-calculator-controller.js` yang menghitung secara dinamis total debit/kredit yang terlihat di layar untuk *instant visual feedback* sebelum server merespons.
   * Controller harus membersihkan event listeners secara aman saat Turbo Frame di-replace (`disconnect()` handling).

#### Constraints & Batasan
* **Zero Full-Page Reload:** Halaman tidak boleh mengalami reload penuh setelah navigasi awal.
* **No Heavy SPA Framework:** Dilarang menggunakan React, Vue, atau Angular. Seluruh UI logic harus bertumpu pada ViewComponent, Hotwire, dan vanilla Stimulus 3.x.
* **Idempotency & Isolation:** Jika koneksi ActionCable putus dan nyambung kembali (*reconnect*), UI harus secara otomatis memulihkan state tanpa meninggalkan elemen "ghost locked".

#### Expected Output
* File komponen: `app/components/audit_matrix/account_row_component.rb` dan template `.html.erb`-nya.
* Controller Rails minimal yang menangani endpoint `adjust` dengan format `turbo_stream`.
* File Stimulus controller: `app/javascript/controllers/matrix_calculator_controller.js`.
* Skema broadcast Turbo Stream pada model ActiveRecord yang menangani update baris dan total agregat.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup Turbo Drive (Visit, Fetch, Render) dan bedanya dengan traditional browser navigation.
- [ ] Anatomi respons HTTP untuk Turbo Frames dan bagaimana Rails merender tanpa layout dokumen utama saat header `Turbo-Frame` hadir.
- [ ] Tujuh aksi standar Turbo Streams (`append`, `prepend`, `replace`, `update`, `remove`, `before`, `after`) dan kapan menggunakan Morphing (`action: :morph`).
- [ ] Siklus hidup Stimulus Controller (`initialize()`, `connect()`, `disconnect()`) beserta trigger pemanggilannya saat DOM dimutasi.
- [ ] Perbedaan Stimulus Targets, Values, dan Classes, serta bagaimana perubahan atribut HTML (`data-*-value`) memicu *Value Changed Callbacks*.
- [ ] Arsitektur internal ViewComponent: isolasi context, kompilasi template ruby, rendering lifecycle, dan pengujian via `render_inline`.
- [ ] Mekanisme enkapsulasi ActionCable channel subscription di balik helper Hotwire `turbo_stream_from`.
- [ ] Batasan teknis Turbo 8 Idiomorph dalam menangani form focus, selection range, dan elemen yang memegang local JavaScript state.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar konfigurasi internal Turbo JavaScript API (cukup pahami event hooks penting seperti `turbo:before-cache`, `turbo:load`, `turbo:submit-end`).
- [ ] Sintaks persis dari helper signature ActionView yang jarang dipakai (cukup rujuk dokumentasi Rails API).
- [ ] Algoritma internal diffing Idiomorph baris-per-baris (cukup pahami prinsip pencocokan ID, tag, dan atribut `data-turbo-permanent`).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan memperbaiki eror Turbo Frame `Content missing` menggunakan network profiling browser DevTools.
- [ ] Mencegah memory leak pada aplikasi Hotwire dengan membersihkan global event listeners, timers, dan instance library pihak ketiga di Stimulus `disconnect()`.
- [ ] Mengonversi ActionView partial monolitik yang lambat menjadi ViewComponent modular yang memiliki unit test komprehensif.
- [ ] Mengimplementasikan *optimistic UI update* sederhana menggunakan Stimulus tanpa menyebabkan desinkronisasi data dengan server.
- [ ] Menangani error validasi form Rails (HTTP 422) secara elegan di dalam Turbo Frames tanpa merusak state elemen halaman lainnya.
- [ ] Mendesain arsitektur broadcast Turbo Streams berskala besar yang aman dari ancaman saturasi antrean background job dan *Redis backplane bottleneck*.