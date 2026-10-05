# BAB-05-Interaction-Design-dan-Mekanika-Perilaku: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji penguasaan konsep, analisis arsitektur interaksi, perancangan state machine UI, serta implementasi mekanika umpan balik (feedback loops) dan micro-interactions pada aplikasi modern.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Konsep Affordance vs Signifier
Jelaskan perbedaan fundamental antara **Affordance** (Don Norman) dan **Signifier** dalam konteks antarmuka digital (GUI), serta berikan contoh konkret elemen input pada web application!

#### Kunci Jawaban & Pembahasan:
- **Affordance:** Hubungan relasional aktual antara sifat fisik/kemampuan suatu objek dengan kemampuan aktor (pengguna) untuk memanipulasinya. Affordance menentukan aksi apa yang secara fisik atau logis *mungkin* dilakukan (contoh: tombol layar sentuh memiliki affordance untuk disentuh/ditekan secara fisik).
- **Signifier:** Sinyal, penanda visual, atau indikator persepsi eksplisit yang mengomunikasikan *keberadaan* affordance tersebut serta cara berinteraksi dengannya (contoh: bevel, bayangan drop-shadow `box-shadow`, label teks "Kirim", ikon panah, atau kursor `pointer`).
- **Contoh GUI:** Sebuah elemen `<div>` murni memiliki affordance teknis untuk diklik via JavaScript handler, tetapi tanpa signifier (seperti elevasi, outline kontras, dan kursor pointer), pengguna tidak mengetahui bahwa elemen tersebut dapat diklik.

---

### Soal 2: Hukum Fitts (Fitts's Law) dalam UI Design
Tuliskan formula dasar Hukum Fitts ($MT = a + b \log_2(2D / W)$) dan jelaskan dua implikasi praktis perancangan tata letak (layout) tombol aksi utama (Primary CTA) pada antarmuka mobile!

#### Kunci Jawaban & Pembahasan:
- **Formula:**
  $$MT = a + b \cdot \log_2\left(\frac{2D}{W}\right) = a + b \cdot ID$$
  Di mana $MT$ adalah Waktu Gerak (*Movement Time*), $D$ adalah jarak (*Distance*) ke target, $W$ adalah lebar/ukuran target (*Width*), serta $ID$ adalah *Index of Difficulty*.
- **Implikasi Praktis pada Mobile UI:**
  1. **Memperbesar Target Area ($W$):** Minimum sentuh standar (misal 48x48 dp atau 44x44 pt sesuai WCAG 2.5.5 / HIG) memperbesar $W$, memperkecil rasio $2D/W$, sehingga meminimalkan $MT$ dan menurunkan angka *miss-tap*.
  2. **Meminimalkan Jarak Jangkauan Jempol ($D$):** Meletakkan CTA utama pada *Thumb Zone* (bagian bawah layar atau sticky bottom bar) mengurangi jarak $D$ dari posisi netral ibu jari pengguna, mempercepat eksekusi aksi secara drastis dibanding menaruhnya di pojok kiri atas (*hard-to-reach zone*).

---

### Soal 3: Komponen Mikro-Interaksi (Dan Saffer)
Sebutkan dan definisikan 4 struktur pembentuk mikro-interaksi menurut model Dan Saffer!

#### Kunci Jawaban & Pembahasan:
1. **Trigger:** Pemicu yang memulai mikro-interaksi, baik berupa *user-initiated* (klik, tap, scroll, swipe) maupun *system-initiated* (notifikasi masuk, kondisi baterai rendah, timer tercapai).
2. **Rules:** Aturan logika bisnis dan state transition yang menentukan apa yang terjadi dan urutan event saat trigger aktif (misal: jika toggle switch digeser ke kanan, aktifkan tema gelap dan simpan preference ke `localStorage`).
3. **Feedback:** Indikator visual, audio, atau haptik yang memberi tahu pengguna apa yang sedang/telah terjadi sesuai rules (misal: perubahan warna latar tombol, bunyi denting halus, haptic vibration).
4. **Loops & Modes:** Parameter meta yang menentukan durasi, perulangan, atau perubahan mode interaksi (misal: animasi berulang saat polling data, atau mode "Do Not Disturb" yang menonaktifkan trigger tertentu).

---

### Soal 4: State Matrix Dasar pada Komponen Interaktif
Sebutkan minimal 5 kondisi (*states*) standar yang wajib didefinisikan oleh Interaction Designer untuk sebuah komponen tombol aksi interaktif!

#### Kunci Jawaban & Pembahasan:
Interaction designer wajib merinci minimal 5 state interaktif berikut:
1. **Default / Idle / Rest:** Kondisi awal sebelum interaksi pengguna.
2. **Hover:** Indikasi kursor desktop berada di atas area batas komponen (menampilkan affordance interaktivitas).
3. **Focused (Keyboard / Accessibility Focus):** Indikator visual fokus navigasi keyboard (`:focus-visible`), wajib memiliki rasio kontras 3:1 terhadap latar belakang.
4. **Active / Pressed:** Umpan balik sesaat ketika tombol ditekan/disentuh (misal scale down 0.98, elevasi berkurang).
5. **Loading / Processing:** Kondisi asinkron ketika aksi sedang dieksekusi sistem (tombol dinonaktifkan dari double-click, indikator spinner atau skeleton dimunculkan).
6. *(Tambahan)* **Disabled:** Kondisi komponen tidak dapat diakses/dieksekusi karena prasyarat form belum terpenuhi.

---

### Soal 5: Latensi & Ambang Persepsi Waktu (Perceived Performance)
Berdasarkan riset Nielsen Norman Group dan standar sistem interaksi HCI, jelaskan perbedaan ambang respon 0.1 detik, 1.0 detik, dan 10 detik!

#### Kunci Jawaban & Pembahasan:
- **0.1 Detik (100 ms):** Batas persepsi reaksi seketika (*instantaneous*). Pengguna merasa kontrol sistem bereaksi langsung terhadap fisik jari/tangannya tanpa jeda (contoh: state press pada button, ripple effect).
- **1.0 Detik (1000 ms):** Batas alur berpikir (*flow of thought*) pengguna tetap tidak terputus. Pengguna menyadari ada jeda pemrosesan, namun fokus mereka masih berada pada tugas aktif tanpa merasa terdistraksi. Diperlukan indikator loading sederhana (seperti spinner) jika melebihi 1 detik.
- **10 Detik:** Batas absolut retensi perhatian pengguna. Melewati 10 detik, pengguna akan meninggalkan alur, membuka tab/aplikasi lain, atau berasumsi sistem mengalami crash/hang. Diperlukan progress bar persentase deterministik, estimasi waktu tersisa, atau proses latar belakang (*background task*).

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6: Finite State Machine (FSM) untuk Form Submission
Rancang Finite State Machine (FSM) yang aman untuk alur pengiriman formulir checkout pembayaran. Identifikasi seluruh State, Event, dan Transisi guna mencegah bug umum seperti *double-spending* atau *race conditions*!

#### Kunci Jawaban & Pembahasan:
```
  [ Idle / Editing ]
         │
         │ Event: SUBMIT_CLICK (Validasi Lolos)
         ▼
    [ Submitting ] ────(Double click diabaikan / Button Disabled)
         │
    ┌────┴────────────────────────┐
    │ Event: API_SUCCESS          │ Event: API_ERROR / TIMEOUT
    ▼                             ▼
[ Success / Confirmed ]      [ Error / Recoverable ]
                                  │
                                  │ Event: RETRY_CLICK / EDIT_INPUT
                                  ▼
                            [ Idle / Editing ]
```
- **States:**
  - `Idle`: Pengguna mengisi form; validasi inline berjalan di sisi klien.
  - `Submitting`: Request mutasi dikirim via network. Tombol bayar dinonaktifkan (`disabled=true`, idempotent token disertakan) untuk memblokir pemicuan ganda.
  - `Success`: Respon 200 OK diterima, UI dialihkan ke invoice atau receipt page.
  - `Error`: Jaringan putus atau saldo tidak cukup. Pesan kesalahan kontekstual dimunculkan, data form tidak di-reset, tombol beralih ke state `Retry`.
- **Mitigasi Race Condition:** Di state `Submitting`, FSM mengabaikan event klik tambahan dan request duplikat dibatalkan via `AbortController`.

---

### Soal 7: Feedforward vs Feedback dalam Kompleksitas Interaksi
Jelaskan perbedaan struktural antara **Feedforward** dan **Feedback**, lalu ilustrasikan penerapannya pada fitur Drag-and-Drop file uploader!

#### Kunci Jawaban & Pembahasan:
- **Feedforward:** Komunikasi proaktif sebelum aksi dieksekusi. Menginformasikan pengguna tentang apa yang akan terjadi jika mereka melakukan aksi tertentu, batas-batas operasi, dan target yang valid.
  - *Penerapan Drag-and-Drop:* Saat file diseret melewati jendela browser, area dropzone menyala dengan outline putus-putus tebal, teks berubah menjadi "Lepaskan file PDF/PNG di sini (Maks 10MB)", dan kursor berubah menjadi ikon tautan/tambah (+).
- **Feedback:** Respon reaktif setelah atau selama aksi dilakukan. Mengonfirmasi bahwa sistem telah mendeteksi aksi dan memperlihatkan hasil sementara/akhir.
  - *Penerapan Drag-and-Drop:* Saat file dilepas, area dropzone langsung menampilkan nama file, icon thumbnail, animasi linear progress upload (0% ke 100%), dan suara notifikasi sukses atau centang hijau setelah file terverifikasi di server.

---

### Soal 8: Hukum Hick-Hyman dan Optimasi Menu Navigasi
Rumuskan Hukum Hick-Hyman ($RT = b \log_2(n + 1)$). Bagaimana arsitek interaksi memanfaatkannya untuk merestrukturisasi dashboard e-commerce dengan 40 sub-fitur agar waktu reaksi pengguna minimal?

#### Kunci Jawaban & Pembahasan:
- **Formula:**
  $$RT = b \cdot \log_2(n + 1)$$
  Di mana $RT$ adalah Waktu Reaksi (*Reaction Time*), $n$ adalah jumlah opsi setara yang disajikan, dan $b$ adalah konstanta empiris kognitif.
- **Strategi Optimasi Interaksi:**
  1. **Hierarchical Categorization (Chunking):** Jangan menampilkan 40 opsi sekaligus secara flat di sidebar. Bagi menjadi 4-5 kategori payung induk (misal: Katalog, Penjualan, Analitik, Konfigurasi). Mengurangi $n$ dari 40 menjadi 4 di level navigasi pertama secara drastis memangkas waktu kognitif ($ \log_2(5) \approx 2.32 $ vs $ \log_2(41) \approx 5.36 $).
  2. **Progressive Disclosure:** Tampilkan sub-menu hanya ketika kategori induk aktif atau dibuka.
  3. **Command Palette / Search Shortcut (Ctrl+K):** Sediakan jalur alternatif untuk *power users* melewati scanning visual melalui pencarian berbasis intent langsung.

---

### Soal 9: Optimistic UI vs Pessimistic UI
Bandingkan paradigma arsitektur interaksi **Optimistic UI** dengan **Pessimistic UI**. Pada skenario apa Optimistic UI berbahaya untuk diterapkan?

#### Kunci Jawaban & Pembahasan:
- **Pessimistic UI:** Sistem menunggu konfirmasi resmi dari server (respons HTTP 200) sebelum memperbarui status antarmuka pengguna.
  - *Keuntungan:* Akurasi data 100% terjamin; tidak memerlukan mekanisme rollback visual.
  - *Kerugian:* Aplikasi terasa lambat dan patah-patah karena terikat latensi jaringan (RTT).
- **Optimistic UI:** Antarmuka langsung memperbarui state visual secara instan seketika trigger disentuh (seolah-olah mutasi server pasti berhasil), sambil mengeksekusi request di latar belakang.
  - *Keuntungan:* *Perceived performance* mendekati 0ms (sangat responsif).
  - *Kerugian:* Membutuhkan state rollback yang kompleks dan notifikasi korektif jika mutasi server gagal.
- **Skenario Berbahaya:** Dilarang keras pada transaksi bernilai tinggi, operasi finansial/transfer dana, otorisasi debit kartu kredit, penghapusan permanen data penting (*hard delete*), atau lelang real-time di mana kegagalan rollback membingungkan persepsi kepemilikan modal pengguna.

---

### Soal 10: Prinsip Gestalt dalam Desain Form Berjenjang
Analisis bagaimana prinsip Gestalt **Proximity (Kedekatan)** dan **Common Region (Kawasan Bersama)** mempengaruhi efisiensi pengisian form panjang (*form completion rate*)!

#### Kunci Jawaban & Pembahasan:
- **Prinsip Proximity:** Elemen-elemen yang berjarak dekat dipahami memiliki hubungan fungsional yang erat. Kesalahan fatal yang sering terjadi adalah label form diletakkan tepat di tengah-tengah antara input atas dan input bawah. Interaction designer harus membuat jarak antara Label dan Input pasangannya jauh lebih rapat (misal 6px) dibanding jarak antar field grup berikutnya (misal 24px), sehingga mata pengguna langsung memetakan asosiasi tanpa salah input.
- **Prinsip Common Region:** Elemen-elemen yang dilingkupi oleh batas visual yang jelas (garis border tipis atau kontras latar belakang card) diasosiasikan sebagai satu kesatuan logis. Dalam form berjenjang (multi-section), mengelompokkan data pengiriman, data pembayaran, dan ringkasan pesanan ke dalam card terpisah mengurangi beban kognitif (*cognitive load*) karena pengguna dapat memproses informasi per blok (*chunk*) alih-alih menghadapi rentetan input tak berujung.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Bug "Ghost Click" dan State Jamming pada Aplikasi Ride-Hailing
- **Konteks:** Tim frontend menerima laporan bahwa pengguna aplikasi pemesanan taksi online secara tidak sengaja memesan 2 hingga 3 armada sekaligus pada kondisi koneksi 3G/Edge yang tidak stabil.
- **Gejala Teknis:** Pengguna menekan tombol "Pesan Sekarang". Karena latensi API tinggi (~3.5 detik), tidak ada perubahan visual seketika. Pengguna merasa sentuhan pertama tidak terdaftar, lalu menekan tombol berulang kali.
- **Tugas Interaction Designer:**
  1. Analisis titik kegagalan interaksi (*Interaction Breakdown Point*).
  2. Rancang transisi micro-interaction dan state handling tombol tersebut.
  3. Tentukan mekanisme umpan balik audio/haptik dan visual yang tepat.

#### Solusi & Rekomendasi:
1. **Analisis Masalah:** Ketiadaan respon seketika (<100ms) melanggar prinsip *instant feedback*. Tombol tetap berada pada state `Idle` saat request HTTP telah meluncur, membuka celah konkurensi klik jamak.
2. **Desain State Machine Tombol:**
   - *T = 0ms:* Saat `touchstart` / `click`, jalankan animasi skala mikro (`scale(0.97)`), trigger haptic feedback ringan (`vibrate(15)`).
   - *T = 50ms:* Ubah state tombol dari `Idle` ke `Processing`. Nonaktifkan pointer events (`pointer-events: none; disabled=true`), ganti label teks dengan spinner berputar deterministik + teks dinamis: "Menghubungi Pengemudi Terdekat...".
   - *Idempotency Header:* Generate UUID transaksi di sisi klien saat formulir dibuka dan kirimkan sebagai `X-Idempotency-Key` ke API backend untuk menjamin request ganda di level server diabaikan.
   - *Timeout Handling:* Jika dalam 15 detik API tidak merespons, transisi ke state `Error/Retry` dengan dialog transparan yang mengonfirmasi bahwa tidak ada saldo yang terpotong.

---

### Skenario 2: Drop-off Tinggi pada Onboarding B2B SaaS dengan Stepper Form
- **Konteks:** Dashboard analitik B2B SaaS mengalami tingkat drop-off sebesar 68% pada langkah ke-3 dari 5 langkah proses konfigurasi organisasi.
- **Temuan Usability:** Langkah 3 meminta konfigurasi integrasi webhook dan API key pihak ketiga yang membutuhkan otorisasi akun eksternal. Pengguna sering beralih tab untuk mengambil token, dan saat kembali, session form mereka me-refresh atau mereka kehilangan konteks di mana mereka berada.
- **Tugas Interaction Designer:**
  1. Rancang arsitektur interaksi baru untuk navigasi wizard/stepper form.
  2. Implementasikan prinsip *Progressive Disclosure* dan *Feedback Preservation*.

#### Solusi & Rekomendasi:
1. **Penerapan Asynchronous Autosave:**
   - Setiap perubahan input harus otomatis tersimpan ke `IndexedDB` / `localStorage` dan di-sync ke draft state backend secara debounced (500ms).
   - Munculkan micro-indicator visual di pojok form: icon awan kecil dengan tooltip status "Draft tersimpan otomatis jam 14:32".
2. **Restrukturisasi Alur dengan Progressive Disclosure:**
   - Jadikan langkah konfigurasi API/Webhook sebagai opsi "Dapat Dilewati (Skip for Now)". Berikan feedforward: *"Anda dapat menghubungkan integrasi ini nanti melalui menu Pengaturan Organisasi"*.
3. **Non-blocking Context Switch:**
   - Sediakan tombol "Salin URL Webhook" dengan feedback visual transisi ikon centang ("Tersalin!") dan popup helper in-app panduan step-by-step tanpa mengharuskan pengguna menutup tab aplikasi utama.

---

### Skenario 3: Revamp Filter Kompleks Multi-Dimensi pada Portal E-Commerce Fashion
- **Konteks:** Portal fashion online memiliki 12 kategori filter (Ukuran, Warna, Material, Merek, Rentang Harga, Diskon, Kategori Acara, dll). Pada antarmuka mobile web, pengguna merasa frustrasi karena setiap kali mencentang satu checkbox ukuran, halaman melakukan refresh/loading query lambat, mereset scroll position ke atas.
- **Tugas Interaction Designer:**
  1. Rancang interaksi filter mobile yang efisien dan ergonomis.
  2. Tentukan pola pembaruan data (Batch Selection vs Instant Apply).

#### Solusi & Rekomendasi:
1. **Pola Bottom Sheet Modal dengan Batch Selection:**
   - Pisahkan interaksi filtering dari view list produk utama menggunakan *Draggable Bottom Sheet*.
   - Jangan melakukan trigger request API per klik checkbox. Terapkan pola *Staged Selection*: pengguna bebas mencentang banyak atribut tanpa terganggu re-render list produk.
2. **Dynamic Live Count Feedforward pada Action Bar:**
   - Di dalam bottom sheet, sediakan fixed footer dengan dua tombol:
     - "Reset" (Secondary, teks netral).
     - "Tampilkan (142 Produk)" (Primary CTA).
   - Di latar belakang, aplikasi menjalankan *lightweight count query* yang mengembalikan estimasi jumlah item yang cocok secara real-time. Tombol CTA secara dinamis memperbarui angka produk saat filter dipilih, memberikan feedforward instan sebelum pengguna berkomitmen menutup modal.
3. **Preservasi Scroll State & Active Tag Pill:**
   - Saat bottom sheet ditutup ("Terapkan"), pertahankan scroll position kategori dan tampilkan deretan *Filter Pills* horizontal yang dapat di-dismiss dengan satu tap langsung di atas katalog produk.

---

## Bagian 4: Practical Chapter Challenge

### Judul Challenge: Perancangan State Machine & Mikro-Interaksi "Swipe-to-Complete / Swipe-to-Delete" Task Item

#### Deskripsi Skenario:
Anda ditugaskan merancang spesifikasi interaksi untuk komponen daftar tugas (*Task Item List*) pada aplikasi produktivitas mobile enterprise. Komponen harus mendukung gestur horizontal swipe dua arah dengan ketentuan:
1. **Swipe Kanan (Right Swipe):** Menandai tugas sebagai "Selesai" (*Mark as Completed*).
2. **Swipe Kiri (Left Swipe):** Menghapus tugas (*Delete Task*) dengan proteksi kesalahan pengguna (*Undo Mechanism*).

#### Spesifikasi Teknis & Kebutuhan Desain:
1. **Threshold & Resistance Physics:**
   - Tentukan nilai batas jarak (drag threshold dalam pixel/persentase) untuk aktivasi aksi.
   - Definisikan kurva resistensi (*rubber-banding / friction*) jika pengguna menarik melebihi batas layar.
2. **State Diagram Komprehensif:**
   - Gambarkan atau tuliskan transisi state: `Resting`, `Dragging`, `Threshold_Reached`, `Releasing_Committed`, `Releasing_Cancelled`, `Executing_Action`, dan `Undo_Window`.
3. **Umpan Balik Visual & Haptic Matrix:**
   - Cantumkan warna background reveal (misal Hijau untuk Complete, Merah untuk Delete), icon scaling, dan trigger haptic (`selection`, `impactLight`, `impactHeavy`).
4. **Mekanisme Reversibilitas (Pemberian Waktu Pembatalan):**
   - Rancang durasi Snackbar/Toast "Item Dihapus" lengkap dengan timer Countdown dan tombol "Urungkan (Undo)".

#### Rubrik Penilaian:
| Kriteria | Skor Maksimal | Deskripsi Evaluasi |
| :--- | :---: | :--- |
| **Kelengkapan State Machine** | 30 | Semua state, event interupsi, dan edge-case (misal swipe batal di tengah jalan) terdokumentasi rapi. |
| **Detail Fisika & Gestur** | 25 | Penentuan threshold persentase, damping factor, dan durasi transisi (ms) dijelaskan secara presisi. |
| **Prinsip Ergonomi & Aksesibilitas** | 25 | Menyediakan fallback alternatif bagi pengguna navigasi non-gestural (keyboard / screen reader accessibility). |
| **Error Recovery (Undo Architecture)** | 20 | Alur penundaan penghapusan permanen dan pemulihan data dirancang tanpa merusak integritas state UI. |

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk mengukur kesiapan Anda sebelum melangkah ke Bab berikutnya:

- [ ] Saya mampu membedakan secara tegas konsep Affordance murni dan Signifier visual dalam desain antarmuka digital.
- [ ] Saya memahami perhitungan matematis dan implikasi tata letak tombol ergonomis berdasarkan Hukum Fitts.
- [ ] Saya mampu menguraikan struktur mikro-interaksi Dan Saffer (Trigger, Rules, Feedback, Loops/Modes) ke dalam spesifikasi UI developer-ready.
- [ ] Saya memahami batas ambang persepsi waktu manusia (100ms, 1s, 10s) dan dapat menentukan kapan harus memakai skeleton loader, progress bar, atau Optimistic UI.
- [ ] Saya mampu memodelkan alur interaksi kompleks menggunakan Finite State Machine (FSM) untuk mencegah bug konkurensi (double submit, race conditions).
- [ ] Saya memahami prinsip Feedforward untuk memandu ekspektasi pengguna sebelum aksi destruktif atau kompleks dijalankan.
- [ ] Saya dapat menerapkan hukum Gestalt (khususnya Proximity dan Common Region) untuk merestrukturisasi layout antarmuka formulir yang padat.
- [ ] Saya mampu merancang sistem micro-interaction dengan error-recovery yang manusiawi (seperti Undo Toast dibanding modal dialog konfirmasi yang memblokir alur).
