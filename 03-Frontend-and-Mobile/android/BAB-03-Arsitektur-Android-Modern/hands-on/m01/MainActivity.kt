Jika state berubah di antara waktu evaluasi `function(prev)` dan eksekusi `compareAndSet`, operasi gagal secara atomik dan loop mengulang evaluasi dengan state terbaru.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. The Clean Architecture Boundaries & DIP

Hukum utama Clean Architecture yang dirumuskan oleh Robert C. Martin menyatakan: **Dependensi kode sumber hanya boleh mengarah ke dalam (*Source code dependencies must point only inward, toward higher-level policies*)**.

* **Entities / Models:** Representasi objek bisnis murni.
* **Use Cases:** Mengorkestrasikan aliran data ke dan dari entitas. Tidak terikat pada platform Android (tidak boleh ada impor `android.content.Context`, `android.os.Bundle`, dsb).
* **Interface Adapters (ViewModel, Presenter, Repository Impl):** Mengonversi data dari format Use Case ke format GUI atau database.
* **Frameworks & Drivers (Compose, Room, Retrofit, Ktor):** Lapisan terluar yang paling sering berubah.

Berdasarkan *Dependency Inversion Principle* (DIP):
* Modul tingkat tinggi (`:core:domain`) tidak boleh bergantung pada modul tingkat rendah (`:core:data`).
* Keduanya harus bergantung pada abstraksi (antarmuka repositori di dalam `:core:domain`).
* Modul tingkat rendah mengimplementasikan abstraksi tersebut.

### 2. Stateflow vs SharedFlow vs Channel untuk Event Handling

Kesalahan arsitektural fatal yang kerap ditemui adalah menggunakan `SharedFlow` untuk memancarkan navigasi atau pesan *one-off error*.

| Komponen | Retensi / Replay | Kapasitas Buffer | Sifat Konsumsi | Skenario Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **`StateFlow`** | Selalu menyimpan 1 nilai terakhir (Konflasi otomatis). | 1 (Konflasi nilai baru jika tidak terkonsumsi). | Multicast (Banyak observer menerima data sama). | **UI State murni.** Representasi visual layar kapan saja. |
| **`SharedFlow`** | Dikonfigurasi via `replay` parameter ($0..n$). | Dikonfigurasi via `extraBufferCapacity`. | Multicast. Emisi tanpa observer akan di-*drop* jika buffer penuh / replay = 0. | **Broadcast Stream.** Contoh: Sinyal log out global, notifikasi *real-time*. |
| **`Channel`** | Tanpa replay default. Mengantre data hingga dikonsumsi. | Sesuai konfigurasi buffer (`RENDEZVOUS`, `BUFFERED`, `UNLIMITED`). | Unicast (Satu event dikonsumsi tepat oleh satu subscriber). | **Side-Effects.** Navigasi, Show Toast, Analytics Events. |

#### Mengapa SharedFlow(replay = 0) Berbahaya untuk Navigasi UI?
Jika ViewModel mengeksekusi navigasi melalui `MutableSharedFlow(replay = 0)` saat fragment/layar sedang berada di latar belakang (*stopped state*), pengamat Compose (`LaunchedEffect` atau lifecycle-aware flow collector) telah berhenti berlangganan (*inactive*). Event tersebut akan langsung dibuang ke kehampaan (*dropped*). Akibatnya, saat pengguna kembali ke aplikasi, aksi navigasi hilang permanen.

Menggunakan `Channel(capacity = Channel.BUFFERED)` yang diekspos sebagai Flow via `receiveAsFlow()` menjamin event diantrekan di memori sampai UI kembali aktif (*resumed*) untuk mengonsumsinya secara tepat satu kali (*guaranteed single-event consumption*).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah fondasi arsitektur MVI + Clean Architecture berbasis Kotlin murni dan Coroutines Flow.

### 1. Core Contract Abstraction
